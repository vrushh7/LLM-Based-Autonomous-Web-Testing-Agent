"""
Main FastAPI Server — Production Upgrade
Orchestrates: LLM → DebugAgent → AutomationEngine → RAG → ReportGenerator
"""

import json
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

import config
from llm_service import llm_service
from automation_engine import automation_engine
from report_generator import report_generator
from rag_store import get_rag_store

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format=config.LOG_FORMAT,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Testing Agent API",
    description="Autonomous browser testing agent powered by LLM + RAG + self-healing",
    version="3.0.0",
)

# ============================================================
# ✅ CORS with proper origins
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS + ["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestRequest(BaseModel):
    instruction: str
    dry_run: bool = False
    force_fresh: bool = False


class HealthResponse(BaseModel):
    status: str
    llm_available: bool
    rag_stats: dict
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "AI Testing Agent API v3.0",
        "features": [
            "RAG-enhanced prompt generation",
            "Self-healing selector correction",
            "Plan → Execute → Observe → Fix → Retry loop",
            "Amazon + Google workflows",
            "Structured HTML/JSON reports",
        ],
        "endpoints": {
            "health":       "GET  /health",
            "run_test":     "POST /api/test",
            "dry_run":      "POST /api/test  (body: {dry_run: true})",
            "history":      "GET  /api/history",
            "html_report":  "GET  /api/report/{test_id}/html",
            "rag_stats":    "GET  /api/rag/stats",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    rag = get_rag_store()
    rag_stats = rag.get_stats()
    llm_available = llm_service.health_check()
    status = "healthy" if llm_available else "degraded"
    message = "All systems operational" if llm_available else (
        "LLM service unavailable. Start Ollama: ollama serve && ollama pull llama3.2:3b"
    )
    return HealthResponse(
        status=status,
        llm_available=llm_available,
        rag_stats=rag_stats,
        message=message,
    )


@app.post("/api/test", tags=["Testing"])
async def run_test(request: TestRequest, background_tasks: BackgroundTasks):
    """
    Execute a test from a natural language instruction.

    Full pipeline:
    1. RAG lookup → reuse past workflow if available
    2. LLM → JSON test plan (with DebugAgent JSON repair)
    3. Playwright execution (plan → execute → observe → self-heal → retry)
    4. RAG update (record result)
    5. Report generation (HTML + JSON + screenshots)
    """
    instruction = request.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="Instruction cannot be empty")

    logger.info(f"[API] ▶ Test request: '{instruction}' (dry_run={request.dry_run})")

    try:
        # Step 1: Generate / retrieve test plan
        llm_result = llm_service.generate_test_steps(
            instruction, force_fresh=request.force_fresh
        )
        if not llm_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Plan generation failed: {llm_result.get('error')}",
            )

        test_plan = llm_result["test_plan"]
        was_repaired = llm_result.get("was_repaired", False)
        validation_issues = llm_result.get("validation_issues", []) or []
        plan_source = test_plan.get("_source", "llm")

        if was_repaired:
            logger.warning(
                f"[API] Plan was repaired ({len(validation_issues)} validation issue(s))."
            )
            for msg in validation_issues:
                logger.info(f"  • {msg}")

        # Dry run: return plan without executing
        if request.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "test_plan": test_plan,
                "plan_source": plan_source,
                "llm_repaired": was_repaired,
                "validation_issues": validation_issues,
            }

        # Step 2: Execute test plan (self-healing inside engine)
        execution_result = await automation_engine.execute_test_plan(test_plan)

        # Step 3: Record in RAG (background task for speed)
        rag = get_rag_store()
        background_tasks.add_task(
            rag.record_workflow,
            instruction,
            test_plan.get("steps", []),
            execution_result.get("success", False),
        )

        # Step 4: Generate report
        report = report_generator.generate_report(
            instruction=instruction,
            test_plan=test_plan,
            execution_result=execution_result,
        )

        summary = execution_result.get("summary", {})
        logger.info(
            f"[API] ✅ Test complete: {report['status']} "
            f"({report['summary']['passed_steps']}/{report['summary']['total_steps']} steps passed) "
            f"| skipped={summary.get('skipped', 0)} duration={summary.get('duration', 0)}s"
        )

        # ============================================================
        # ✅ Response wrapped in "report" field for frontend compatibility
        # ============================================================
        return {
            "success": True,
            "report": {
                "success": execution_result.get("success", False),
                "status": report['status'],
                "steps": execution_result.get("steps", []),
                "duration": execution_result.get("duration", 0),
                "summary": report['summary'],
                "instruction": instruction,
                "test_id": execution_result.get("test_folder", "").split("/")[-1] if execution_result.get("test_folder") else None,
                "timestamp": report.get('timestamp')
            },
            "test_plan": test_plan,
            "plan_source": plan_source,
            "llm_repaired": was_repaired,
            "validation_issues": validation_issues,
            "execution_summary": summary,
            "test_folder": execution_result.get("test_folder"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[API] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history", tags=["Testing"])
async def get_test_history(limit: int = 10):
    try:
        history = report_generator.get_report_history(limit=limit)
        return {"success": True, "count": len(history), "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/report/{test_id}", tags=["Testing"])
async def get_report(test_id: str):
    try:
        report_file = config.REPORTS_DIR / f"{test_id}.json"
        if not report_file.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        return {"success": True, "report": report}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/report/{test_id}/html", response_class=HTMLResponse, tags=["Testing"])
async def get_html_report(test_id: str):
    try:
        report_file = config.REPORTS_DIR / f"{test_id}.json"
        if not report_file.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        return HTMLResponse(content=report_generator.format_html_report(report))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ✅ FIXED: Screenshot endpoint handles nested paths
# ============================================================
@app.get("/api/screenshot/{path:path}", tags=["Testing"])
async def get_screenshot(path: str):
    try:
        screenshot_path = config.SCREENSHOTS_DIR / path
        if not screenshot_path.exists():
            raise HTTPException(status_code=404, detail=f"Screenshot not found: {path}")
        return FileResponse(screenshot_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rag/stats", tags=["RAG"])
async def rag_stats():
    """Return RAG store statistics."""
    try:
        rag = get_rag_store()
        return {"success": True, "stats": rag.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/rag/clear", tags=["RAG"])
async def clear_rag():
    """Clear the RAG store (resets selector/workflow memory). Use with caution."""
    try:
        import shutil
        from pathlib import Path
        rag_path = Path(__file__).parent / "rag_data"
        if rag_path.exists():
            shutil.rmtree(rag_path)
        global _rag_store_instance
        from rag_store import _rag_store_instance
        _rag_store_instance = None
        return {"success": True, "message": "RAG store cleared and reinitialized."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"[API] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc), "detail": "Unexpected error"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     AI-Powered Autonomous Testing Agent  v3.0               ║
║                                                              ║
║  Server  : http://{config.HOST}:{config.PORT}                            ║
║  API Docs: http://{config.HOST}:{config.PORT}/docs                       ║
║  Health  : http://{config.HOST}:{config.PORT}/health                     ║
║                                                              ║
║  Features: RAG | Self-Healing | Google | Amazon             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

 Prerequisites:
   • Ollama running  → ollama serve
   • Model pulled   → ollama pull llama3.2:3b

 Press Ctrl+C to stop.
""")
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
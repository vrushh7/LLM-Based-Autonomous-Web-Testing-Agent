"""
Main FastAPI Server — Production v4.0
Orchestrates: LLM → DebugAgent → AutomationEngine → RAG → ReportGenerator

Supports ALL 8 Requirements:
1. Amazon/Flipkart product search & compare
2. Continuous monitoring (stock, crypto, product)
3. Google Images high-res download
4. YouTube automation
5. Flight comparison
6. Smart login
7. Dynamic recovery
8. Autonomous decision-making
"""

import json
import logging
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
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

# ── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Autonomous Agent API",
    description=(
        "Autonomous browser agent: Product Search | Monitoring | "
        "Images | YouTube | Flights | Smart Login"
    ),
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────

class TestRequest(BaseModel):
    instruction: str
    dry_run: bool = False
    force_fresh: bool = False


class MonitorRequest(BaseModel):
    instruction: str
    duration_seconds: int = 60
    poll_interval: int = 30


class HumanInputRequest(BaseModel):
    session_id: str
    value: str


class HealthResponse(BaseModel):
    status: str
    llm_available: bool
    rag_stats: dict
    message: str


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "AI Autonomous Agent API v4.0",
        "features": [
            "✅ Amazon/Flipkart: search, filter, sort, variants, quantity, add to cart, buy now",
            "✅ Smart compound queries (under ₹X, rating > Y, best product)",
            "✅ Continuous monitoring (stock, crypto, product) with autonomous triggers",
            "✅ Google Images: search + click Nth + download high-res",
            "✅ YouTube: search, play, like, fullscreen, comments, subscribe, settings",
            "✅ Flight comparison across platforms",
            "✅ Smart login: username → Next → password → submit + CAPTCHA/OTP fallback",
            "✅ Dynamic failure recovery with SmartFinder (5 fallback layers)",
            "✅ RAG-powered learning from past workflows",
        ],
        "endpoints": {
            "health":           "GET  /health",
            "run_test":         "POST /api/test",
            "dry_run":          "POST /api/test  (body: {dry_run: true})",
            "monitor":          "POST /api/monitor",
            "stop_monitoring":  "POST /api/monitor/stop",
            "human_input":      "POST /api/human-input",
            "history":          "GET  /api/history",
            "report_json":      "GET  /api/report/{test_id}",
            "report_html":      "GET  /api/report/{test_id}/html",
            "rag_stats":        "GET  /api/rag/stats",
            "rag_clear":        "DELETE /api/rag/clear",
            "screenshot":       "GET  /api/screenshot/{path}",
        },
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    rag = get_rag_store()
    rag_stats = rag.get_stats()
    llm_available = llm_service.health_check()
    status = "healthy" if llm_available else "degraded"
    message = (
        "All systems operational" if llm_available
        else "LLM unavailable. Run: ollama serve && ollama pull llama3.2:3b"
    )
    return HealthResponse(
        status=status,
        llm_available=llm_available,
        rag_stats=rag_stats,
        message=message,
    )


# ── Test Execution ────────────────────────────────────────────────────────────

@app.post("/api/test", tags=["Testing"])
async def run_test(request: TestRequest, background_tasks: BackgroundTasks):
    """
    Execute any natural-language instruction. Examples:
    - "Search iPhone 15 on Amazon, 256GB Black, add to cart"
    - "Find coffee machine under ₹6000 rating above 4, add best to cart"
    - "Open YouTube, search 'python tutorial', play, like, fullscreen"
    - "Search Google Images for sunset, download high-res"
    - "Compare flights from DEL to BOM"
    - "Login to https://example.com username test@x.com password abc123"
    - "Monitor Bitcoin, notify if below $50000"
    """
    instruction = request.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="Instruction cannot be empty")

    logger.info(f"[API] ▶ run_test: '{instruction}' dry_run={request.dry_run}")

    try:
        llm_result = llm_service.generate_test_steps(
            instruction, force_fresh=request.force_fresh
        )
        if not llm_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Plan generation failed: {llm_result.get('error')}",
            )

        test_plan          = llm_result["test_plan"]
        was_repaired       = llm_result.get("was_repaired", False)
        validation_issues  = llm_result.get("validation_issues", []) or []
        plan_source        = test_plan.get("_source", "llm")
        bypassed_llm       = llm_result.get("bypassed_llm", False)

        if was_repaired:
            logger.warning(f"[API] Plan repaired ({len(validation_issues)} issue(s))")

        if request.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "test_plan": test_plan,
                "plan_source": plan_source,
                "bypassed_llm": bypassed_llm,
                "llm_repaired": was_repaired,
                "validation_issues": validation_issues,
            }

        execution_result = await automation_engine.execute_test_plan(test_plan)

        rag = get_rag_store()
        background_tasks.add_task(
            rag.record_workflow,
            instruction,
            test_plan.get("steps", []),
            execution_result.get("success", False),
        )

        report = report_generator.generate_report(
            instruction=instruction,
            test_plan=test_plan,
            execution_result=execution_result,
        )

        summary = execution_result.get("summary", {})
        logger.info(
            f"[API] ✅ Complete: {report['status']} "
            f"({report['summary']['passed_steps']}/{report['summary']['total_steps']} steps) "
            f"duration={summary.get('duration', 0):.1f}s"
        )

        test_folder = execution_result.get("test_folder", "")
        test_id = Path(test_folder).name if test_folder else None

        return {
            "success": True,
            "report": {
                "success":     execution_result.get("success", False),
                "status":      report["status"],
                "steps":       execution_result.get("steps", []),
                "duration":    execution_result.get("duration", 0),
                "summary":     report["summary"],
                "instruction": instruction,
                "test_id":     test_id,
                "timestamp":   report.get("timestamp"),
            },
            "test_plan":         test_plan,
            "plan_source":       plan_source,
            "bypassed_llm":      bypassed_llm,
            "llm_repaired":      was_repaired,
            "validation_issues": validation_issues,
            "execution_summary": summary,
            "test_folder":       test_folder,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[API] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Monitoring ────────────────────────────────────────────────────────────────

@app.post("/api/monitor", tags=["Monitoring"])
async def start_monitoring(request: MonitorRequest, background_tasks: BackgroundTasks):
    """
    Start continuous monitoring. Examples:
    - "Monitor Bitcoin, notify if below $50,000"
    - "Monitor Tesla stock, buy if drops 5%"
    - "Monitor PS5 price on Amazon, notify if below ₹45,000"
    """
    instruction = request.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="Instruction cannot be empty")

    logger.info(f"[API] ▶ monitor: '{instruction}' for {request.duration_seconds}s")

    try:
        llm_result = llm_service.generate_test_steps(instruction, force_fresh=False)
        if not llm_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Plan generation failed: {llm_result.get('error')}",
            )

        test_plan = llm_result["test_plan"]

        # Inject duration/interval into start_monitoring steps
        for step in test_plan.get("steps", []):
            if step.get("action") == "start_monitoring":
                for monitor in step.get("monitors", []):
                    monitor.setdefault("interval", request.poll_interval)
                step["duration_seconds"] = request.duration_seconds

        execution_result = await automation_engine.execute_test_plan(test_plan)

        triggers = [
            s for s in execution_result.get("steps", [])
            if "trigger" in str(s).lower()
        ]

        return {
            "success":             execution_result.get("success", False),
            "monitoring_duration": request.duration_seconds,
            "poll_interval":       request.poll_interval,
            "triggers":            triggers,
            "summary":             execution_result.get("summary", {}),
            "monitor_status":      execution_result.get("variables", {}).get("monitor_status", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[API] Monitoring error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/stop", tags=["Monitoring"])
async def stop_monitoring():
    """Stop all active monitoring tasks."""
    try:
        await automation_engine.monitor_manager.stop_all()
        return {"success": True, "message": "All monitoring tasks stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Human Input (CAPTCHA / OTP unblock) ──────────────────────────────────────

@app.post("/api/human-input", tags=["Testing"])
async def provide_human_input(request: HumanInputRequest):
    """
    Unblock a session waiting for CAPTCHA or OTP input.
    Call this from your UI when the user has completed the challenge.
    """
    try:
        automation_engine.provide_human_input(request.session_id, request.value)
        return {"success": True, "message": f"Input provided to session {request.session_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── History & Reports ─────────────────────────────────────────────────────────

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


# ── Screenshot Serving ────────────────────────────────────────────────────────

@app.get("/api/screenshot/{path:path}", tags=["Testing"])
async def get_screenshot(path: str):
    """Serve screenshots; accepts full paths, relative paths, or just filenames."""
    try:
        from urllib.parse import unquote
        decoded = unquote(path).replace("\\", "/")
        filename = Path(decoded).name

        candidates = [
            Path(decoded),
            config.SCREENSHOTS_DIR / filename,
            Path("screenshots") / filename,
            Path(__file__).parent / "screenshots" / filename,
        ]

        # Also search recursively in SCREENSHOTS_DIR
        if not any(p.exists() for p in candidates):
            for found in config.SCREENSHOTS_DIR.rglob(f"*{filename}"):
                if found.is_file():
                    candidates.insert(0, found)
                    break

        for candidate in candidates:
            if candidate and candidate.exists() and candidate.is_file():
                logger.info(f"Serving screenshot: {candidate}")
                return FileResponse(candidate)

        raise HTTPException(status_code=404, detail=f"Screenshot not found: {filename}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── RAG ───────────────────────────────────────────────────────────────────────

@app.get("/api/rag/stats", tags=["RAG"])
async def rag_stats():
    try:
        rag = get_rag_store()
        return {"success": True, "stats": rag.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/rag/clear", tags=["RAG"])
async def clear_rag():
    """Clear and reinitialise the RAG store. Use with caution."""
    try:
        rag_path = config.RAG_DATA_DIR
        if rag_path.exists():
            shutil.rmtree(rag_path)
        rag_path.mkdir(exist_ok=True)

        import rag_store
        rag_store._rag_store_instance = None
        get_rag_store()

        return {"success": True, "message": "RAG store cleared and reinitialized."}
    except Exception as e:
        logger.exception(f"[API] Failed to clear RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Global Error Handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"[API] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc), "detail": "Unexpected server error"},
    )


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting AI Autonomous Agent API v4.0")
    get_rag_store()
    if not llm_service.health_check():
        logger.warning("⚠️  LLM service unavailable. Run: ollama serve && ollama pull llama3.2:3b")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Shutting down AI Autonomous Agent API")
    await automation_engine.cleanup_all()


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   🤖  AI-Powered Autonomous Agent v4.0                                       ║
║                                                                              ║
║   ✅  Amazon/Flipkart Search, Filter, Sort, Variants, Cart                  ║
║   ✅  Smart Compound Queries (price + rating + best pick)                    ║
║   ✅  Monitoring: Stock / Crypto / Product with Autonomous Triggers          ║
║   ✅  Google Images: Search + Click Nth + High-Res Download                 ║
║   ✅  YouTube: Search, Play, Like, Fullscreen, Comments                     ║
║   ✅  Flight Comparison                                                      ║
║   ✅  Smart Login: Multi-step + CAPTCHA/OTP Human Fallback                  ║
║   ✅  Dynamic Recovery (SmartFinder 5-layer fallback)                       ║
║                                                                              ║
║   Server  : http://{config.HOST}:{config.PORT}
║   API Docs: http://{config.HOST}:{config.PORT}/docs
║   Health  : http://{config.HOST}:{config.PORT}/health
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Prerequisites:
  • ollama serve
  • ollama pull {config.LLM_MODEL}

Press Ctrl+C to stop.
""")
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
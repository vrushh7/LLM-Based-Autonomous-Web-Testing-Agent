"""
Report Generator Module
Generates formatted test execution reports.

Upgrades:
- Includes per-step screenshots (with <img> tags in HTML)
- Reads metadata.json from test folder for enriched step info
- Shows PASS / FAIL badge per step
- Overall summary with progress bar
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates test execution reports"""

    def __init__(self):
        self.reports_dir = config.REPORTS_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report(
        self,
        instruction: str,
        test_plan: Dict,
        execution_result: Dict,
    ) -> Dict:
        """
        Generate a comprehensive test report and persist it as JSON.

        Returns the report dict.
        """
        test_id = self._generate_test_id()

        # Enrich steps from metadata file if available
        steps = self._load_enriched_steps(execution_result)

        summary = self._generate_summary(steps)

        report = {
            "test_id": test_id,
            "timestamp": execution_result.get("timestamp", datetime.now().isoformat()),
            "instruction": instruction,
            "status": execution_result.get("status", "UNKNOWN"),
            "success": execution_result.get("success", False),
            "duration": round(execution_result.get("duration", 0), 2),
            "url": test_plan.get("url"),
            "steps": steps,
            "summary": summary,
            "screenshot": execution_result.get("screenshot"),
            "test_folder": execution_result.get("test_folder"),
            "metadata_file": execution_result.get("metadata_file"),
            "error_message": (
                execution_result.get("message")
                if not execution_result.get("success")
                else None
            ),
        }

        self._save_report(report)
        logger.info(f"[ReportGenerator] Report saved: {test_id}")
        return report

    def get_report_history(self, limit: int = 10) -> List[Dict]:
        """Return the most recent test reports."""
        report_files = sorted(
            self.reports_dir.glob("TEST_*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )[:limit]

        reports = []
        for filepath in report_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    reports.append(json.load(f))
            except Exception:
                continue
        return reports

    def format_html_report(self, report: Dict) -> str:
        """
        Generate a rich HTML report with:
        - Pass/fail badges per step
        - Embedded screenshots
        - Summary bar chart
        """
        status_color = "#22c55e" if report["success"] else "#ef4444"

        steps_html = self._build_steps_html(report.get("steps", []))
        summary = report.get("summary", {})
        total = summary.get("total_steps", 0)
        passed = summary.get("passed_steps", 0)
        failed = summary.get("failed_steps", 0)
        rate = summary.get("success_rate", "0%")
        pass_pct = (passed / total * 100) if total > 0 else 0

        # Failure screenshot at top if present
        failure_img_html = ""
        if report.get("screenshot"):
            failure_img_html = f"""
            <div class="section">
                <h2>Failure Screenshot</h2>
                <img src="{report['screenshot']}" alt="Failure Screenshot" class="screenshot">
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Test Report — {report['test_id']}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #222; }}
    .container {{ max-width: 960px; margin: 40px auto; background: #fff; border-radius: 12px;
                  box-shadow: 0 4px 24px rgba(0,0,0,.10); overflow: hidden; }}
    .header {{ padding: 32px 40px; border-bottom: 1px solid #eee; }}
    .header h1 {{ font-size: 1.6rem; color: #1a1a2e; }}
    .badge {{ display: inline-block; padding: 4px 14px; border-radius: 20px; font-weight: 700;
              font-size: .85rem; color: #fff; background: {status_color}; margin-left: 12px; }}
    .section {{ padding: 28px 40px; border-bottom: 1px solid #f0f0f0; }}
    .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px 30px; }}
    .meta-item {{ font-size: .9rem; }}
    .meta-item span {{ font-weight: 600; }}
    /* Progress bar */
    .progress-bar-wrap {{ background: #f0f0f0; border-radius: 8px; height: 14px; margin: 10px 0; overflow: hidden; }}
    .progress-bar {{ height: 100%; background: {status_color}; border-radius: 8px;
                     width: {pass_pct:.1f}%; transition: width .4s; }}
    /* Steps */
    .step-card {{ background: #fafafa; border: 1px solid #e8e8e8; border-radius: 8px;
                  margin: 10px 0; overflow: hidden; }}
    .step-header {{ display: flex; align-items: center; padding: 12px 18px; gap: 10px; }}
    .step-num {{ font-weight: 700; color: #555; min-width: 56px; }}
    .step-action {{ font-size: .78rem; background: #e9eef7; color: #3b5bdb;
                    border-radius: 4px; padding: 2px 8px; font-weight: 600; text-transform: uppercase; }}
    .step-desc {{ flex: 1; font-size: .92rem; }}
    .step-status {{ font-weight: 700; font-size: .82rem; padding: 3px 10px; border-radius: 12px; color: #fff; }}
    .status-success {{ background: #22c55e; }}
    .status-failed  {{ background: #ef4444; }}
    .step-body {{ padding: 0 18px 14px; }}
    .step-ts {{ font-size: .76rem; color: #888; margin-bottom: 6px; }}
    .step-error {{ background: #fff0f0; border-left: 4px solid #ef4444; padding: 8px 12px;
                   font-size: .84rem; color: #c0392b; border-radius: 0 4px 4px 0; margin-bottom: 8px; }}
    .screenshot {{ max-width: 100%; border: 1px solid #ddd; border-radius: 6px;
                   margin-top: 8px; display: block; }}
    h2 {{ font-size: 1.15rem; color: #1a1a2e; margin-bottom: 16px; }}
    .summary-stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 12px; }}
    .stat {{ background: #f5f7ff; border-radius: 8px; padding: 12px 20px; text-align: center; min-width: 100px; }}
    .stat .value {{ font-size: 1.6rem; font-weight: 700; color: {status_color}; }}
    .stat .label {{ font-size: .78rem; color: #666; }}
  </style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>AI Test Report <span class="badge">{report.get('status', 'UNKNOWN')}</span></h1>
  </div>

  <!-- Meta -->
  <div class="section">
    <h2>Test Details</h2>
    <div class="meta-grid">
      <div class="meta-item"><span>Test ID:</span> {report['test_id']}</div>
      <div class="meta-item"><span>Timestamp:</span> {report['timestamp']}</div>
      <div class="meta-item"><span>Duration:</span> {report['duration']:.2f}s</div>
      <div class="meta-item"><span>URL:</span> {report.get('url') or 'N/A'}</div>
      <div class="meta-item" style="grid-column:1/-1"><span>Instruction:</span> {report['instruction']}</div>
    </div>
  </div>

  <!-- Summary -->
  <div class="section">
    <h2>Summary</h2>
    <div class="summary-stats">
      <div class="stat"><div class="value">{total}</div><div class="label">Total Steps</div></div>
      <div class="stat"><div class="value" style="color:#22c55e">{passed}</div><div class="label">Passed</div></div>
      <div class="stat"><div class="value" style="color:#ef4444">{failed}</div><div class="label">Failed</div></div>
      <div class="stat"><div class="value">{rate}</div><div class="label">Success Rate</div></div>
    </div>
    <div class="progress-bar-wrap"><div class="progress-bar"></div></div>
    <small style="color:#888">{passed} of {total} steps passed</small>
  </div>

  {failure_img_html}

  <!-- Steps -->
  <div class="section">
    <h2>Step Details</h2>
    {steps_html}
  </div>

</div>
</body>
</html>"""

        return html

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_test_id(self) -> str:
        return f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _load_enriched_steps(self, execution_result: Dict) -> List[Dict]:
        """
        Prefer the metadata.json written by the engine (richer data).
        Fall back to execution_result['steps'] if unavailable.
        """
        metadata_file = execution_result.get("metadata_file")
        if metadata_file:
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    return [self._format_step(s) for s in raw]
            except Exception as e:
                logger.warning(f"[ReportGenerator] Could not read metadata: {e}")

        return [self._format_step(s) for s in execution_result.get("steps", [])]

    def _format_step(self, step: Dict) -> Dict:
        """Normalise a step dict for the report."""
        return {
            "step_number": step.get("step", step.get("step_number", 0)),
            "action": step.get("action", "unknown"),
            "description": step.get("description", ""),
            "status": step.get("status", "unknown"),
            "timestamp": step.get("timestamp", ""),
            "screenshot": step.get("screenshot"),
            "error": step.get("error"),
        }

    def _generate_summary(self, steps: List[Dict]) -> Dict:
        total = len(steps)
        passed = sum(1 for s in steps if s.get("status") == "success")
        failed = total - passed
        return {
            "total_steps": total,
            "passed_steps": passed,
            "failed_steps": failed,
            "success_rate": f"{(passed / total * 100) if total > 0 else 0:.1f}%",
        }

    def _save_report(self, report: Dict):
        filepath = self.reports_dir / f"{report['test_id']}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def _build_steps_html(self, steps: List[Dict]) -> str:
        if not steps:
            return "<p>No steps recorded.</p>"

        html_parts = []
        for step in steps:
            status = step.get("status", "unknown")
            status_class = "status-success" if status == "success" else "status-failed"
            status_label = "✓ PASS" if status == "success" else "✗ FAIL"

            error_html = ""
            if step.get("error"):
                error_html = f'<div class="step-error">⚠ {step["error"]}</div>'

            screenshot_html = ""
            ss = step.get("screenshot")
            if ss and Path(ss).exists():
                screenshot_html = f'<img src="{ss}" alt="Step screenshot" class="screenshot">'

            ts_html = ""
            if step.get("timestamp"):
                ts_html = f'<div class="step-ts">🕐 {step["timestamp"]}</div>'

            html_parts.append(f"""
    <div class="step-card">
      <div class="step-header">
        <span class="step-num">Step {step.get('step_number', '?')}</span>
        <span class="step-action">{step.get('action', '')}</span>
        <span class="step-desc">{step.get('description', '')}</span>
        <span class="step-status {status_class}">{status_label}</span>
      </div>
      <div class="step-body">
        {ts_html}
        {error_html}
        {screenshot_html}
      </div>
    </div>""")

        return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
report_generator = ReportGenerator()
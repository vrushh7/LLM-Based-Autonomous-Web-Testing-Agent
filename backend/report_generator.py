"""
Report Generator Module — Enhanced for ALL 8 Requirements
Generates formatted test execution reports.

Upgrades:
- Includes per-step screenshots (with <img> tags in HTML)
- Reads metadata.json from test folder for enriched step info
- Shows PASS / FAIL badge per step
- Overall summary with progress bar
- ✅ NEW: Monitoring trigger reports
- ✅ NEW: Flight comparison results
- ✅ NEW: YouTube interaction metrics
- ✅ NEW: Product comparison tables
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

        # Extract requirement-specific data
        monitoring_data = self._extract_monitoring_data(steps)
        flight_data = self._extract_flight_data(execution_result)
        product_data = self._extract_product_data(execution_result)

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
            # New fields for requirements
            "monitoring": monitoring_data,
            "flights": flight_data,
            "products": product_data,
            "variables": execution_result.get("variables", {}),
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
        - ✅ Monitoring trigger tables
        - ✅ Flight comparison results
        - ✅ Product comparison tables
        """
        status_color = "#22c55e" if report["success"] else "#ef4444"

        steps_html = self._build_steps_html(report.get("steps", []))
        summary = report.get("summary", {})
        total = summary.get("total_steps", 0)
        passed = summary.get("passed_steps", 0)
        failed = summary.get("failed_steps", 0)
        rate = summary.get("success_rate", "0%")
        pass_pct = (passed / total * 100) if total > 0 else 0

        # Monitoring section
        monitoring_html = self._build_monitoring_html(report.get("monitoring", {}))

        # Flights section
        flights_html = self._build_flights_html(report.get("flights", {}))

        # Products section
        products_html = self._build_products_html(report.get("products", {}))

        # Variables section
        variables_html = self._build_variables_html(report.get("variables", {}))

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
    .header {{ padding: 32px 40px; border-bottom: 1px solid #eee; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
    .header h1 {{ font-size: 1.6rem; color: #fff; }}
    .badge {{ display: inline-block; padding: 4px 14px; border-radius: 20px; font-weight: 700;
              font-size: .85rem; color: #fff; background: {status_color}; margin-left: 12px; }}
    .section {{ padding: 28px 40px; border-bottom: 1px solid #f0f0f0; }}
    .section:last-child {{ border-bottom: none; }}
    .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px 30px; }}
    .meta-item {{ font-size: .9rem; }}
    .meta-item span {{ font-weight: 600; color: #667eea; }}
    .progress-bar-wrap {{ background: #f0f0f0; border-radius: 8px; height: 14px; margin: 10px 0; overflow: hidden; }}
    .progress-bar {{ height: 100%; background: {status_color}; border-radius: 8px;
                     width: {pass_pct:.1f}%; transition: width .4s; }}
    .step-card {{ background: #fafafa; border: 1px solid #e8e8e8; border-radius: 8px;
                  margin: 10px 0; overflow: hidden; }}
    .step-header {{ display: flex; align-items: center; padding: 12px 18px; gap: 10px; flex-wrap: wrap; }}
    .step-num {{ font-weight: 700; color: #555; min-width: 56px; }}
    .step-action {{ font-size: .78rem; background: #e9eef7; color: #3b5bdb;
                    border-radius: 4px; padding: 2px 8px; font-weight: 600; text-transform: uppercase; }}
    .step-desc {{ flex: 1; font-size: .92rem; }}
    .step-status {{ font-weight: 700; font-size: .82rem; padding: 3px 10px; border-radius: 12px; color: #fff; }}
    .status-success {{ background: #22c55e; }}
    .status-failed  {{ background: #ef4444; }}
    .status-skipped {{ background: #f59e0b; }}
    .step-body {{ padding: 0 18px 14px; }}
    .step-ts {{ font-size: .76rem; color: #888; margin-bottom: 6px; }}
    .step-error {{ background: #fff0f0; border-left: 4px solid #ef4444; padding: 8px 12px;
                   font-size: .84rem; color: #c0392b; border-radius: 0 4px 4px 0; margin-bottom: 8px; }}
    .screenshot {{ max-width: 100%; border: 1px solid #ddd; border-radius: 6px;
                   margin-top: 8px; display: block; }}
    h2 {{ font-size: 1.15rem; color: #1a1a2e; margin-bottom: 16px; border-left: 4px solid #667eea; padding-left: 12px; }}
    .summary-stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 12px; }}
    .stat {{ background: #f5f7ff; border-radius: 8px; padding: 12px 20px; text-align: center; min-width: 100px; }}
    .stat .value {{ font-size: 1.6rem; font-weight: 700; color: {status_color}; }}
    .stat .label {{ font-size: .78rem; color: #666; }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
    th {{ background: #f8f9fa; font-weight: 600; color: #333; }}
    .trigger-item {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 10px 15px; margin: 8px 0; border-radius: 6px; }}
    .trigger-time {{ font-size: .76rem; color: #888; }}
    .price-down {{ color: #ef4444; font-weight: 600; }}
    .price-up {{ color: #22c55e; font-weight: 600; }}
    .best-product {{ background: #dcfce7; font-weight: 600; }}
  </style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>🤖 AI Autonomous Test Report <span class="badge">{report.get('status', 'UNKNOWN')}</span></h1>
  </div>

  <!-- Meta -->
  <div class="section">
    <h2>📋 Test Details</h2>
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
    <h2>📊 Execution Summary</h2>
    <div class="summary-stats">
      <div class="stat"><div class="value">{total}</div><div class="label">Total Steps</div></div>
      <div class="stat"><div class="value" style="color:#22c55e">{passed}</div><div class="label">Passed</div></div>
      <div class="stat"><div class="value" style="color:#ef4444">{failed}</div><div class="label">Failed</div></div>
      <div class="stat"><div class="value">{rate}</div><div class="label">Success Rate</div></div>
    </div>
    <div class="progress-bar-wrap"><div class="progress-bar"></div></div>
    <small style="color:#888">{passed} of {total} steps passed</small>
  </div>

  {monitoring_html}
  {flights_html}
  {products_html}
  {variables_html}
  {failure_img_html}

  <!-- Steps -->
  <div class="section">
    <h2>📝 Step Details</h2>
    {steps_html}
  </div>

</div>
</body>
</html>"""

        return html

    # ------------------------------------------------------------------
    # Requirement-specific HTML builders
    # ------------------------------------------------------------------

    def _build_monitoring_html(self, monitoring: Dict) -> str:
        """Build HTML for monitoring triggers section"""
        if not monitoring:
            return ""

        triggers = monitoring.get("triggers", [])
        if not triggers:
            return ""

        triggers_html = ""
        for trigger in triggers:
            triggers_html += f"""
            <div class="trigger-item">
                <strong>🔔 {trigger.get('item', 'Unknown')}</strong><br>
                Condition: {trigger.get('condition', 'N/A')} → Value: <span class="{'price-down' if 'drop' in str(trigger.get('condition')).lower() else 'price-up'}">{trigger.get('value', 'N/A')}</span><br>
                Action: {trigger.get('action', 'notify')}<br>
                <span class="trigger-time">Triggered at: {trigger.get('timestamp', 'N/A')}</span>
            </div>"""

        return f"""
        <div class="section">
            <h2>📈 Monitoring Triggers ({len(triggers)} triggered)</h2>
            {triggers_html}
        </div>"""

    def _build_flights_html(self, flights: Dict) -> str:
        """Build HTML for flight comparison results"""
        if not flights:
            return ""

        cheapest = flights.get("cheapest")
        fastest = flights.get("fastest")
        results = flights.get("results", [])

        if not cheapest and not fastest and not results:
            return ""

        html_parts = ['<div class="section"><h2>✈️ Flight Comparison</h2>']

        if cheapest:
            html_parts.append(f"""
            <div class="best-product" style="padding: 12px; border-radius: 8px; margin-bottom: 15px;">
                <strong>💰 Cheapest Flight:</strong> {cheapest.get('airline', 'N/A')} - ₹{cheapest.get('price', 'N/A')}<br>
                Duration: {cheapest.get('duration', 'N/A')} | Stops: {cheapest.get('stops', 'N/A')}
            </div>""")

        if fastest:
            html_parts.append(f"""
            <div style="padding: 12px; background: #e0f2fe; border-radius: 8px; margin-bottom: 15px;">
                <strong>⚡ Fastest Flight:</strong> {fastest.get('airline', 'N/A')} - {fastest.get('duration', 'N/A')}<br>
                Price: ₹{fastest.get('price', 'N/A')} | Stops: {fastest.get('stops', 'N/A')}
            </div>""")

        if results:
            rows = ""
            for r in results[:5]:
                rows += f"""
                <tr>
                    <td>{r.get('airline', 'N/A')}</td>
                    <td>₹{r.get('price', 'N/A')}</td>
                    <td>{r.get('duration', 'N/A')}</td>
                    <td>{r.get('stops', 'N/A')}</td>
                </tr>"""
            html_parts.append(f"""
            <table>
                <thead><tr><th>Airline</th><th>Price</th><th>Duration</th><th>Stops</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>""")

        html_parts.append('</div>')
        return "\n".join(html_parts)

    def _build_products_html(self, products: Dict) -> str:
        """Build HTML for product comparison results"""
        if not products:
            return ""

        best = products.get("best_product")
        all_products = products.get("all_products", [])

        if not best and not all_products:
            return ""

        html_parts = ['<div class="section"><h2>🛍️ Product Comparison</h2>']

        if best:
            html_parts.append(f"""
            <div class="best-product" style="padding: 12px; border-radius: 8px; margin-bottom: 15px;">
                <strong>🏆 Best Product:</strong> {best.get('name', 'N/A')}<br>
                Price: ₹{best.get('price', 'N/A')} | Rating: {best.get('rating', 'N/A')} ⭐<br>
                Platform: {best.get('platform', 'N/A')}
            </div>""")

        if all_products:
            rows = ""
            for p in all_products[:5]:
                rows += f"""
                <tr>
                    <td>{p.get('name', 'N/A')[:50]}</td>
                    <td>₹{p.get('price', 'N/A')}</td>
                    <td>{p.get('rating', 'N/A')} ⭐</td>
                    <td>{p.get('platform', 'N/A')}</td>
                </tr>"""
            html_parts.append(f"""
            <table>
                <thead><tr><th>Product</th><th>Price</th><th>Rating</th><th>Platform</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>""")

        html_parts.append('</div>')
        return "\n".join(html_parts)

    def _build_variables_html(self, variables: Dict) -> str:
        """Build HTML for extracted variables"""
        if not variables:
            return ""

        vars_html = "<div class='section'><h2>📌 Extracted Variables</h2><table><thead><tr><th>Variable</th><th>Value</th></tr></thead><tbody>"
        for key, value in variables.items():
            if key.startswith("_"):
                continue
            val_str = str(value)[:100]
            vars_html += f"<tr><td><code>{key}</code></td><td>{val_str}</td></tr>"
        vars_html += "</tbody></table></div>"

        return vars_html

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    def _extract_monitoring_data(self, steps: List[Dict]) -> Dict:
        """Extract monitoring triggers from execution steps"""
        triggers = []
        for step in steps:
            if step.get("action") == "check_monitors" and step.get("result"):
                result = step.get("result", {})
                pending = result.get("pending_purchase")
                if pending:
                    triggers.append(pending)
                for key, value in result.items():
                    if key.startswith("notification_"):
                        triggers.append({"item": key.replace("notification_", ""), "message": value})
        return {"triggers": triggers}

    def _extract_flight_data(self, execution_result: Dict) -> Dict:
        """Extract flight comparison results"""
        variables = execution_result.get("variables", {})
        return {
            "cheapest": variables.get("cheapest_flight"),
            "fastest": variables.get("fastest_flight"),
            "results": variables.get("flight_results", []),
        }

    def _extract_product_data(self, execution_result: Dict) -> Dict:
        """Extract product comparison results"""
        variables = execution_result.get("variables", {})
        return {
            "best_product": variables.get("best_product"),
            "all_products": variables.get("all_products", []),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_test_id(self) -> str:
        return f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _load_enriched_steps(self, execution_result: Dict) -> List[Dict]:
        """Prefer the metadata.json written by the engine (richer data)."""
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
            "result": step.get("result"),  # For monitor results
        }

    def _generate_summary(self, steps: List[Dict]) -> Dict:
        total = len(steps)
        passed = sum(1 for s in steps if s.get("status") == "success")
        failed = sum(1 for s in steps if s.get("status") == "failed")
        skipped = sum(1 for s in steps if s.get("status") == "skipped")
        return {
            "total_steps": total,
            "passed_steps": passed,
            "failed_steps": failed,
            "skipped_steps": skipped,
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
            if status == "success":
                status_class = "status-success"
                status_label = "✓ PASS"
            elif status == "failed":
                status_class = "status-failed"
                status_label = "✗ FAIL"
            else:
                status_class = "status-skipped"
                status_label = "⤷ SKIP"

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
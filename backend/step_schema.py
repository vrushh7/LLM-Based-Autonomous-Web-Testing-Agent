"""
Step Schema Validation
----------------------
Single source of truth for what a valid step looks like.

Public API:
    validate_and_repair_plan(plan_dict, instruction="") -> (clean_plan, issues)

`clean_plan` is ALWAYS a dict with at least one safe step (never raises).
`issues` is a list of human-readable validation messages (may be empty).

Goals:
- Reject/repair malformed steps BEFORE they reach the automation engine.
- Guarantee navigate steps always have a valid absolute URL.
- Guarantee fill/click/etc. have non-empty selectors.
- Enforce the Google-Images "search → click images tab → wait → click image → (download)"
  flow when the instruction asks for images.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ACTIONS = set(getattr(config, "VALID_ACTIONS", [
    "navigate", "click", "fill", "press", "wait",
    "assert", "download", "scroll", "hover", "select", "extract",
]))

DEFAULT_NAVIGATE_URL = getattr(config, "DEFAULT_NAVIGATE_URL", "https://www.google.com")

# Actions that MUST carry a non-empty selector
SELECTOR_REQUIRED = {"click", "fill", "assert", "hover", "select", "extract"}

# Reasonable per-action defaults applied during repair
ACTION_DEFAULTS = {
    "wait": {"duration": 2000},
    "press": {"key": "Enter"},
    "scroll": {"direction": "down", "amount": 300},
    "assert": {"assertion_type": "visible"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize_url(url: str) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    # Reject obviously bogus values
    if "." not in url.split("//", 1)[-1]:
        return None
    return url


def _detect_intent_url(instruction: str) -> str:
    """Pick a sensible default URL from the instruction's domain hints."""
    if not instruction:
        return DEFAULT_NAVIGATE_URL
    instr = instruction.lower()
    if "amazon" in instr:
        return "https://www.amazon.in"
    if "youtube" in instr:
        return "https://www.youtube.com"
    if "wikipedia" in instr:
        return "https://www.wikipedia.org"
    if "bing" in instr:
        return "https://www.bing.com"
    return DEFAULT_NAVIGATE_URL


def _wants_images(instruction: str) -> bool:
    if not instruction:
        return False
    return bool(
        re.search(r"\bimages?\b", instruction, re.IGNORECASE)
        or re.search(r"\bpictures?\b", instruction, re.IGNORECASE)
        or re.search(r"\bphotos?\b", instruction, re.IGNORECASE)
        or "images tab" in instruction.lower()
    )


def _wants_download(instruction: str) -> bool:
    if not instruction:
        return False
    return bool(
        re.search(r"\bdownload\b", instruction, re.IGNORECASE)
        or re.search(r"\bsave\s+(?:the\s+)?image\b", instruction, re.IGNORECASE)
    )


def _is_google_plan(plan: Dict, instruction: str) -> bool:
    base = (plan.get("url") or "").lower()
    if "google.com" in base:
        return True
    for step in plan.get("steps", []):
        if step.get("action") == "navigate" and "google.com" in (step.get("url") or "").lower():
            return True
    return "google" in (instruction or "").lower()


# ---------------------------------------------------------------------------
# Per-step repair
# ---------------------------------------------------------------------------

def _repair_step(
    step: Dict[str, Any],
    idx: int,
    instruction: str,
    issues: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Repair a single step in place. Returns the repaired step,
    or None if the step is unrecoverable and should be dropped.
    """
    if not isinstance(step, dict):
        issues.append(f"step[{idx}]: not an object — dropped")
        return None

    # --- action ---
    action = str(step.get("action", "")).strip().lower()
    if action not in VALID_ACTIONS:
        issues.append(f"step[{idx}]: invalid action '{action}' — dropped")
        return None
    step["action"] = action

    # --- description ---
    if _is_blank(step.get("description")):
        step["description"] = f"Step {idx + 1}: {action}"

    # --- per-action defaults ---
    for k, v in ACTION_DEFAULTS.get(action, {}).items():
        step.setdefault(k, v)

    # --- per-action validation ---
    if action == "navigate":
        url = _normalize_url(step.get("url", ""))
        if not url:
            fallback = _detect_intent_url(instruction)
            issues.append(
                f"step[{idx}]: navigate missing/invalid url '{step.get('url')}' "
                f"— defaulted to {fallback}"
            )
            url = fallback
        step["url"] = url
        # selector/value/key are irrelevant for navigate
        step.pop("selector", None)

    elif action == "fill":
        if _is_blank(step.get("selector")):
            issues.append(f"step[{idx}]: fill missing selector — dropped")
            return None
        if "value" not in step or step["value"] is None:
            step["value"] = ""

    elif action == "press":
        key = step.get("key")
        if _is_blank(key):
            step["key"] = "Enter"

    elif action == "wait":
        try:
            step["duration"] = max(0, int(step.get("duration", 2000)))
        except (TypeError, ValueError):
            issues.append(f"step[{idx}]: invalid wait duration — defaulted to 2000ms")
            step["duration"] = 2000

    elif action in ("click", "hover", "assert", "select", "extract"):
        if _is_blank(step.get("selector")):
            issues.append(f"step[{idx}]: {action} missing selector — dropped")
            return None
        if action == "select" and "value" not in step:
            step["value"] = ""
        if action == "extract":
            step.setdefault("variable", f"extracted_{idx + 1}")
            step.setdefault("attribute", "textContent")

    elif action == "scroll":
        try:
            step["amount"] = int(step.get("amount", 300))
        except (TypeError, ValueError):
            step["amount"] = 300
        if step.get("direction") not in ("up", "down"):
            step["direction"] = "down"

    elif action == "download":
        # download has no required fields in our engine
        pass

    return step


# ---------------------------------------------------------------------------
# Plan-level enforcement
# ---------------------------------------------------------------------------

def _ensure_first_step_is_navigate(
    steps: List[Dict],
    instruction: str,
    plan_url: Optional[str],
    issues: List[str],
) -> List[Dict]:
    if steps and steps[0].get("action") == "navigate":
        return steps
    target = _normalize_url(plan_url or "") or _detect_intent_url(instruction)
    issues.append(f"plan: missing leading navigate — inserted navigate to {target}")
    return [{
        "action": "navigate",
        "description": f"Navigate to {target}",
        "url": target,
    }] + steps


def _enforce_google_images_flow(
    steps: List[Dict],
    instruction: str,
    issues: List[str],
) -> List[Dict]:
    """
    For Google-image instructions, ensure the canonical sequence after the
    initial search exists:
        ... press Enter → wait →
        click Images tab → wait →
        click first image → wait →
        (download if requested)
    """
    if not _wants_images(instruction):
        return steps

    has_images_click = any(
        s.get("action") == "click"
        and (
            "tbm=isch" in (s.get("selector") or "")
            or "images" in (s.get("description") or "").lower()
        )
        for s in steps
    )
    has_image_pick = any(
        s.get("action") == "click"
        and (
            "img" in (s.get("selector") or "").lower()
            or "first image" in (s.get("description") or "").lower()
        )
        for s in steps
    )
    has_download = any(s.get("action") == "download" for s in steps)
    wants_dl = _wants_download(instruction)

    appended: List[Dict] = []

    if not has_images_click:
        issues.append("plan: Google Images flow missing — appended Images-tab click")
        appended += [
            {"action": "click", "description": "Click Images tab",
             "selector": "a[href*='tbm=isch']"},
            {"action": "wait", "description": "Wait for image grid", "duration": 2000},
        ]

    if not has_image_pick:
        issues.append("plan: Google Images flow missing — appended first-image click")
        appended += [
            {"action": "click", "description": "Click first image",
             "selector": "img.Q4LuWd"},
            {"action": "wait", "description": "Wait for image preview", "duration": 2000},
        ]

    if wants_dl and not has_download:
        issues.append("plan: download requested but missing — appended download")
        appended += [
            {"action": "download", "description": "Download image"},
        ]

    if appended:
        steps = steps + appended
    return steps


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_and_repair_plan(
    plan: Optional[Dict[str, Any]],
    instruction: str = "",
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate, repair, and enrich a test plan. Never raises.

    Returns:
        (clean_plan, issues)

    `clean_plan` always contains:
        - "url"   : Optional[str]
        - "steps" : List[Dict] with at least one navigate step
    """
    issues: List[str] = []

    if not isinstance(plan, dict):
        issues.append("plan: not a dict — replaced with default navigate plan")
        plan = {}

    raw_steps = plan.get("steps")
    if not isinstance(raw_steps, list):
        issues.append("plan: 'steps' missing or not a list — initialised empty")
        raw_steps = []

    repaired: List[Dict] = []
    for idx, step in enumerate(raw_steps):
        fixed = _repair_step(dict(step) if isinstance(step, dict) else step,
                             idx, instruction, issues)
        if fixed is not None:
            repaired.append(fixed)

    repaired = _ensure_first_step_is_navigate(
        repaired, instruction, plan.get("url"), issues
    )

    if _is_google_plan({"url": plan.get("url"), "steps": repaired}, instruction):
        repaired = _enforce_google_images_flow(repaired, instruction, issues)

    clean = {
        "url": _normalize_url(plan.get("url") or "") or repaired[0].get("url"),
        "steps": repaired,
    }
    # Preserve any extra metadata (e.g. _source) the caller set
    for k, v in plan.items():
        if k not in clean:
            clean[k] = v

    if issues:
        logger.info(f"[StepSchema] Plan repaired with {len(issues)} issue(s):")
        for msg in issues:
            logger.info(f"  • {msg}")
    else:
        logger.debug("[StepSchema] Plan validated cleanly.")

    return clean, issues

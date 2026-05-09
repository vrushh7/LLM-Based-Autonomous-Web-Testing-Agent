"""
Step Schema Validation — v4.0
Single source of truth for valid step structure.

VALID_ACTIONS mirrors automation_engine._execute_step exactly:
  Basic browser, ecommerce (search/sort/filter/click/variant/qty/cart/buy),
  images, youtube, login, monitoring, flights, human-input.

Public API:
    validate_and_repair_plan(plan_dict, instruction="") -> (clean_plan, issues)

Always returns a dict with at least one safe step. Never raises.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import config

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_ACTIONS = {
    # Basic browser
    "navigate", "click", "fill", "press", "wait", "assert",
    "scroll", "hover", "select", "extract", "type", "download",
    # Ecommerce – search & sort
    "search", "apply_sort", "auto_sort",
    "apply_price_filter", "apply_rating_filter",
    # Ecommerce – product selection
    "click_product_index", "click_product_name",
    "select_variant", "select_quantity",
    # Ecommerce – cart / buy
    "add_to_cart", "buy_now", "get_products", "smart_find_and_add_best",
    # Images
    "search_images", "click_google_image", "download_highres",
    # YouTube
    "youtube_search", "youtube_interact",
    # Login
    "smart_login",
    # Flights
    "compare_flights",
    # Monitoring
    "start_monitoring", "check_monitors", "stop_monitoring",
    # Human input
    "request_human_input", "provide_human_input",
    # Legacy alias kept for RAG compatibility
    "search_products",
}

DEFAULT_NAVIGATE_URL: str = getattr(config, "DEFAULT_NAVIGATE_URL", "https://www.google.com")

# Actions that MUST have a non-empty selector
SELECTOR_REQUIRED = {"click", "fill", "assert", "hover", "select", "extract"}

# Sane per-action defaults applied during repair
ACTION_DEFAULTS: Dict[str, Dict] = {
    "wait":                   {"duration": 2000},
    "press":                  {"key": "Enter"},
    "scroll":                 {"direction": "down", "amount": 300},
    "assert":                 {"assertion_type": "visible"},
    "search":                 {"platform": "amazon"},
    "search_products":        {"platform": "amazon"},
    "apply_sort":             {"sort_type": "rating",  "platform": "amazon"},
    "auto_sort":              {"platform": "amazon"},
    "apply_price_filter":     {"max_price": 999999, "min_price": 0, "platform": "amazon"},
    "apply_rating_filter":    {"min_rating": 4.0,   "platform": "amazon"},
    "click_product_index":    {"index": 1,  "platform": "amazon"},
    "click_product_name":     {"platform": "amazon"},
    "select_variant":         {"platform": "amazon"},
    "select_quantity":        {"quantity": 1, "platform": "amazon"},
    "add_to_cart":            {"quantity": 1, "platform": "amazon"},
    "buy_now":                {"quantity": 1, "platform": "amazon"},
    "smart_find_and_add_best":{"min_rating": 0.0, "limit": 20, "platform": "amazon"},
    "click_google_image":     {"index": 1},
    "youtube_search":         {"skip_shorts": True},
    "youtube_interact":       {"interaction": "like"},
    "compare_flights":        {"origin": "DEL", "destination": "BOM", "date": "tomorrow"},
    "start_monitoring":       {"monitors": []},
    "request_human_input":    {"prompt": "Human input required"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    if "." not in url.split("//", 1)[-1]:
        return None
    return url


def _detect_intent_url(instruction: str) -> str:
    if not instruction:
        return DEFAULT_NAVIGATE_URL
    il = instruction.lower()
    if "amazon"    in il: return "https://www.amazon.in"
    if "flipkart"  in il: return "https://www.flipkart.com"
    if "youtube"   in il: return "https://www.youtube.com"
    if "wikipedia" in il: return "https://www.wikipedia.org"
    if "bing"      in il: return "https://www.bing.com"
    if "makemytrip"in il or "flight" in il: return "https://www.makemytrip.com"
    if "google"    in il: return "https://www.google.com"
    return DEFAULT_NAVIGATE_URL


def _extract_query(instruction: str) -> str:
    try:
        from rag_store import extract_search_term
        return extract_search_term(instruction) or "search"
    except Exception:
        return "search"


def _is_monitoring_plan(steps: List[Dict]) -> bool:
    return any(s.get("action") == "start_monitoring" for s in steps)


def _wants_images(instruction: str) -> bool:
    if not instruction:
        return False
    return bool(
        re.search(r"\bimages?\b",   instruction, re.IGNORECASE)
        or re.search(r"\bpictures?\b", instruction, re.IGNORECASE)
        or re.search(r"\bphotos?\b",   instruction, re.IGNORECASE)
    )


def _wants_download(instruction: str) -> bool:
    if not instruction:
        return False
    return bool(
        re.search(r"\bdownload\b", instruction, re.IGNORECASE)
        or re.search(r"\bsave\s+(?:the\s+)?image\b", instruction, re.IGNORECASE)
    )


# ── Per-step Repair ───────────────────────────────────────────────────────────

def _repair_step(
    step: Dict[str, Any],
    idx: int,
    instruction: str,
    issues: List[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(step, dict):
        issues.append(f"step[{idx}]: not an object — dropped")
        return None

    action = str(step.get("action", "")).strip().lower()
    if action not in VALID_ACTIONS:
        issues.append(f"step[{idx}]: invalid action '{action}' — dropped")
        return None
    step["action"] = action

    # Description
    if _is_blank(step.get("description")):
        step["description"] = f"Step {idx + 1}: {action}"

    # Apply per-action defaults
    for k, v in ACTION_DEFAULTS.get(action, {}).items():
        step.setdefault(k, v)

    # ── navigate ──────────────────────────────────────────────────────────────
    if action == "navigate":
        url = _normalize_url(step.get("url", ""))
        if not url:
            fallback = _detect_intent_url(instruction)
            issues.append(f"step[{idx}]: navigate has invalid url — defaulted to {fallback}")
            url = fallback
        step["url"] = url
        step.pop("selector", None)

    # ── fill ──────────────────────────────────────────────────────────────────
    elif action == "fill":
        if _is_blank(step.get("selector")):
            issues.append(f"step[{idx}]: fill missing selector — dropped")
            return None
        step.setdefault("value", "")

    # ── press ─────────────────────────────────────────────────────────────────
    elif action == "press":
        if _is_blank(step.get("key")):
            step["key"] = "Enter"

    # ── wait ──────────────────────────────────────────────────────────────────
    elif action == "wait":
        try:
            step["duration"] = max(0, int(step.get("duration", 2000)))
        except (TypeError, ValueError):
            issues.append(f"step[{idx}]: invalid wait duration — defaulted to 2000ms")
            step["duration"] = 2000

    # ── click / hover / assert / select / extract ─────────────────────────────
    elif action in ("click", "hover", "assert", "select", "extract"):
        if _is_blank(step.get("selector")):
            issues.append(f"step[{idx}]: {action} missing selector — dropped")
            return None
        if action == "select":
            step.setdefault("value", "")
        if action == "extract":
            step.setdefault("variable",  f"extracted_{idx + 1}")
            step.setdefault("attribute", "textContent")

    # ── scroll ────────────────────────────────────────────────────────────────
    elif action == "scroll":
        try:
            step["amount"] = int(step.get("amount", 300))
        except (TypeError, ValueError):
            step["amount"] = 300
        if step.get("direction") not in ("up", "down"):
            step["direction"] = "down"

    # ── search / search_products ──────────────────────────────────────────────
    elif action in ("search", "search_products"):
        if _is_blank(step.get("query")):
            q = _extract_query(instruction)
            step["query"] = q
            issues.append(f"step[{idx}]: {action} missing query — set to '{q}'")
        step.setdefault("platform", "amazon")

    # ── apply_sort ────────────────────────────────────────────────────────────
    elif action == "apply_sort":
        step.setdefault("sort_type", "rating")
        step.setdefault("platform",  "amazon")

    # ── apply_price_filter ────────────────────────────────────────────────────
    elif action == "apply_price_filter":
        step.setdefault("max_price", 999999)
        step.setdefault("min_price", 0)
        step.setdefault("platform",  "amazon")

    # ── apply_rating_filter ───────────────────────────────────────────────────
    elif action == "apply_rating_filter":
        step.setdefault("min_rating", 4.0)
        step.setdefault("platform",   "amazon")

    # ── click_product_index ───────────────────────────────────────────────────
    elif action == "click_product_index":
        step.setdefault("index",    1)
        step.setdefault("platform", "amazon")

    # ── click_product_name ────────────────────────────────────────────────────
    elif action == "click_product_name":
        if _is_blank(step.get("product_name")):
            step["product_name"] = _extract_query(instruction)
            issues.append(f"step[{idx}]: click_product_name missing product_name — extracted from instruction")
        step.setdefault("platform", "amazon")

    # ── select_variant ────────────────────────────────────────────────────────
    elif action == "select_variant":
        if _is_blank(step.get("variant")):
            step["variant"] = ""
            issues.append(f"step[{idx}]: select_variant missing variant")
        step.setdefault("platform", "amazon")

    # ── select_quantity ───────────────────────────────────────────────────────
    elif action == "select_quantity":
        try:
            step["quantity"] = max(1, int(step.get("quantity", 1)))
        except (TypeError, ValueError):
            step["quantity"] = 1
        step.setdefault("platform", "amazon")

    # ── add_to_cart / buy_now ─────────────────────────────────────────────────
    elif action in ("add_to_cart", "buy_now"):
        try:
            step["quantity"] = max(1, int(step.get("quantity", 1)))
        except (TypeError, ValueError):
            step["quantity"] = 1
        step.setdefault("platform", "amazon")

    # ── smart_find_and_add_best ───────────────────────────────────────────────
    elif action == "smart_find_and_add_best":
        step.setdefault("min_rating", 0.0)
        step.setdefault("limit",      20)
        step.setdefault("platform",   "amazon")

    # ── search_images ─────────────────────────────────────────────────────────
    elif action == "search_images":
        if _is_blank(step.get("query")):
            q = _extract_query(instruction)
            step["query"] = q
            issues.append(f"step[{idx}]: search_images missing query — set to '{q}'")

    # ── click_google_image ────────────────────────────────────────────────────
    elif action == "click_google_image":
        step.setdefault("index", 1)

    # ── download_highres — no required fields ─────────────────────────────────

    # ── youtube_search ────────────────────────────────────────────────────────
    elif action == "youtube_search":
        if _is_blank(step.get("query")):
            q = _extract_query(instruction)
            step["query"] = q
            issues.append(f"step[{idx}]: youtube_search missing query — set to '{q}'")
        step.setdefault("skip_shorts", True)

    # ── youtube_interact ──────────────────────────────────────────────────────
    elif action == "youtube_interact":
        if _is_blank(step.get("interaction")):
            desc = step.get("description", "").lower()
            if   "like"        in desc: step["interaction"] = "like"
            elif "comment"     in desc: step["interaction"] = "open_comments"
            elif "scroll"      in desc: step["interaction"] = "scroll_comments"
            elif "fullscreen"  in desc: step["interaction"] = "fullscreen"
            elif "subscribe"   in desc: step["interaction"] = "subscribe"
            elif "settings"    in desc: step["interaction"] = "settings"
            elif "mute"        in desc: step["interaction"] = "mute"
            elif "pause"       in desc: step["interaction"] = "pause"
            else:                       step["interaction"] = "like"
            issues.append(f"step[{idx}]: youtube_interact missing interaction — defaulted to '{step['interaction']}'")

    # ── smart_login ───────────────────────────────────────────────────────────
    elif action == "smart_login":
        if _is_blank(step.get("username")):
            m = re.search(r'(?:username|user|email)\s+(\S+)', instruction, re.IGNORECASE)
            step["username"] = m.group(1) if m else "testuser"
            issues.append(f"step[{idx}]: smart_login missing username — set to '{step['username']}'")
        if _is_blank(step.get("password")):
            m = re.search(r'(?:password|pass|pwd)\s+(\S+)', instruction, re.IGNORECASE)
            step["password"] = m.group(1) if m else "password123"
            issues.append(f"step[{idx}]: smart_login missing password — set from instruction or default")

    # ── compare_flights ───────────────────────────────────────────────────────
    elif action == "compare_flights":
        if _is_blank(step.get("origin")):
            m = re.search(r'from\s+([A-Z]{3})', instruction, re.IGNORECASE)
            step["origin"] = m.group(1).upper() if m else "DEL"
            issues.append(f"step[{idx}]: compare_flights missing origin — set to '{step['origin']}'")
        if _is_blank(step.get("destination")):
            m = re.search(r'to\s+([A-Z]{3})', instruction, re.IGNORECASE)
            step["destination"] = m.group(1).upper() if m else "BOM"
            issues.append(f"step[{idx}]: compare_flights missing destination — set to '{step['destination']}'")
        step.setdefault("date", "tomorrow")

    # ── start_monitoring ──────────────────────────────────────────────────────
    elif action == "start_monitoring":
        if not step.get("monitors"):
            il = instruction.lower()
            if "ps5" in il:
                monitor = {"type": "ecommerce", "id": "PS5",     "condition": "below",        "threshold": 45000, "action": "notify",   "interval": 30}
            elif "tesla" in il:
                monitor = {"type": "stock",     "id": "TSLA",    "condition": "drops_percent", "threshold": 5,     "action": "buy_now",  "interval": 30}
            elif "bitcoin" in il or "btc" in il:
                monitor = {"type": "crypto",    "id": "bitcoin", "condition": "below",         "threshold": 50000, "action": "notify",   "interval": 30}
            elif "ethereum" in il or "eth" in il:
                monitor = {"type": "crypto",    "id": "ethereum","condition": "below",         "threshold": 3000,  "action": "notify",   "interval": 30}
            else:
                monitor = {"type": "crypto",    "id": "bitcoin", "condition": "below",         "threshold": 50000, "action": "notify",   "interval": 30}
                issues.append(f"step[{idx}]: start_monitoring missing monitors — added default bitcoin monitor")
            step["monitors"] = [monitor]

    # ── check_monitors / stop_monitoring — no required fields ─────────────────
    # ── request_human_input ───────────────────────────────────────────────────
    elif action == "request_human_input":
        step.setdefault("prompt", "Human input required")

    # ── provide_human_input ───────────────────────────────────────────────────
    elif action == "provide_human_input":
        step.setdefault("value", "")

    return step


# ── Plan-level Enforcement ────────────────────────────────────────────────────

def _ensure_first_step_navigate(
    steps: List[Dict],
    instruction: str,
    plan_url: Optional[str],
    issues: List[str],
) -> List[Dict]:
    """Monitoring-only plans skip this; all others must start with navigate."""
    if _is_monitoring_plan(steps):
        return steps
    if steps and steps[0].get("action") == "navigate":
        return steps

    target = _normalize_url(plan_url or "") or _detect_intent_url(instruction)
    issues.append(f"plan: missing leading navigate — inserted navigate to {target}")
    return [{"action": "navigate", "description": f"Navigate to {target}", "url": target}] + steps


def _enforce_google_images_flow(
    steps: List[Dict],
    instruction: str,
    issues: List[str],
) -> List[Dict]:
    if not _wants_images(instruction):
        return steps

    has_search_images    = any(s.get("action") == "search_images"    for s in steps)
    has_download_highres = any(s.get("action") == "download_highres" for s in steps)

    appended: List[Dict] = []

    if not has_search_images:
        q = _extract_query(instruction)
        issues.append("plan: images flow missing search_images — appended")
        appended += [
            {"action": "search_images",    "description": f"Search images: {q}", "query": q},
            {"action": "wait",             "description": "Wait for images",      "duration": 3000},
            {"action": "click_google_image","description": "Click first image",   "index": 1},
        ]

    if not has_download_highres and _wants_download(instruction):
        issues.append("plan: download requested but missing download_highres — appended")
        appended.append({"action": "download_highres", "description": "Download high-resolution image"})

    return steps + appended


# ── Public API ────────────────────────────────────────────────────────────────

def validate_and_repair_plan(
    plan: Optional[Dict[str, Any]],
    instruction: str = "",
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate, repair, and enrich a test plan. Never raises.

    Returns:
        (clean_plan, issues)

    `clean_plan` always has:
        - "steps": List[Dict]  (at least one safe step)
        - "url":   Optional[str]
    """
    issues: List[str] = []

    if not isinstance(plan, dict):
        issues.append("plan: not a dict — replaced with empty plan")
        plan = {}

    raw_steps = plan.get("steps")
    if not isinstance(raw_steps, list):
        issues.append("plan: 'steps' missing or not a list — initialised empty")
        raw_steps = []

    # Repair individual steps
    repaired: List[Dict] = []
    for idx, step in enumerate(raw_steps):
        fixed = _repair_step(
            dict(step) if isinstance(step, dict) else step,
            idx, instruction, issues,
        )
        if fixed is not None:
            repaired.append(fixed)

    # Plan-level rules
    repaired = _ensure_first_step_navigate(repaired, instruction, plan.get("url"), issues)

    # Google Images flow enforcement
    il = instruction.lower()
    if "google" in il or not any(
        k in il for k in ["amazon", "flipkart", "youtube", "flight", "monitor"]
    ):
        repaired = _enforce_google_images_flow(repaired, instruction, issues)

    clean: Dict[str, Any] = {
        "url":   _normalize_url(plan.get("url") or "")
                 or (repaired[0].get("url") if repaired else None),
        "steps": repaired,
    }
    # Preserve extra metadata (_source, etc.)
    for k, v in plan.items():
        if k not in clean:
            clean[k] = v

    if issues:
        logger.info(f"[StepSchema] Plan repaired ({len(issues)} issue(s)):")
        for msg in issues:
            logger.info(f"  • {msg}")
    else:
        logger.debug("[StepSchema] Plan validated cleanly.")

    return clean, issues
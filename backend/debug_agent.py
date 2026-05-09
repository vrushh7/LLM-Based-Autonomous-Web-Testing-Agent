"""
Debug Agent — v4.0
Fixes invalid JSON from LLM output and heals broken steps/selectors.

VALID_ACTIONS aligned with automation_engine._execute_step dispatcher:
  Basic browser, ecommerce (search/sort/filter/click/variant/qty/cart/buy),
  images, youtube, login, monitoring, flights, human-input.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Selector Fallback Pools ───────────────────────────────────────────────────

SELECTOR_FALLBACKS: Dict[str, list] = {
    "search": [
        "textarea[name='q']",
        "input[name='q']",
        "input[type='search']",
        "input[placeholder*='Search' i]",
        "[role='searchbox']",
        "input[aria-label*='search' i]",
        "textarea",
        "input[id='twotabsearchtextbox']",   # Amazon
        "input._2P_LnL",                      # Flipkart
    ],
    "submit": [
        "input[type='submit']",
        "button[type='submit']",
        "button[aria-label*='search' i]",
        "[role='button'][aria-label*='Search' i]",
        "input[value='Google Search']",
        "input[id='nav-search-submit-button']",  # Amazon
        "button._2i2sHZ",                        # Flipkart
    ],
    "button": [
        "button",
        "input[type='button']",
        "[role='button']",
    ],
    "link":  ["a[href]"],
    "image": ["img", "[role='img']", "a img"],
    "images_tab": [
        "a[href*='tbm=isch']",
        "text=Images",
        "[aria-label='Images']",
        "a:has-text('Images')",
    ],
    "download": [
        "a[download]",
        "a[href$='.jpg']",
        "a[href$='.png']",
        "a[href$='.jpeg']",
        "img",
    ],
    "cart": [
        "input[id='add-to-cart-button']",
        "button[id='add-to-cart-button']",
        "[data-action='add-to-cart']",
        "button:has-text('Add to Cart')",
        "button._2KpZ6l",   # Flipkart
    ],
    "youtube_search": [
        "input#search",
        "input[name='search_query']",
        "input[aria-label='Search']",
    ],
    "youtube_video": [
        "#dismissible ytd-video-renderer a#thumbnail",
        "ytd-video-renderer a#thumbnail",
        "a#video-title",
    ],
    "product": [
        "div[data-component-type='s-search-result'] h2 a",  # Amazon
        "div._1AtVbE a._1fQZEK",                            # Flipkart
        "div.s-result-item h2 a",
    ],
    "login_username": [
        "input[type='email']",
        "input[name='email']",
        "input[name='username']",
        "input[placeholder*='Email' i]",
        "input[placeholder*='Username' i]",
        "#email", "#username",
    ],
    "login_password": [
        "input[type='password']",
        "input[name='password']",
        "input[placeholder*='Password' i]",
        "#password",
    ],
    "login_button": [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Sign in')",
        "#loginButton", "#signInButton",
    ],
}

_BAD_SELECTOR_PATTERNS = [
    r"^\s*$", r"^null$", r"^none$", r"^n/a$", r"^undefined$",
    r"^selector$", r"^\.\s*$", r"^#\s*$", r"^css selector$", r"^<.*>$",
]

# ── Full action set matching automation_engine._execute_step ─────────────────
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
    # Ecommerce – cart/buy
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
    # Legacy aliases kept for RAG compatibility
    "search_products",
}


# ── DebugAgent ────────────────────────────────────────────────────────────────

class DebugAgent:

    # ── JSON Repair ───────────────────────────────────────────────────────────

    def fix_json_string(self, raw: str) -> Tuple[Optional[Dict], bool]:
        if not raw or not raw.strip():
            logger.warning("[DebugAgent] Empty LLM response.")
            return None, False

        attempts = [
            ("raw",                    raw),
            ("stripped_markdown",      self._strip_markdown(raw)),
            ("extracted_block",        self._extract_json_block(raw)),
            ("fixed_quotes",           self._fix_quotes(raw)),
            ("removed_trailing_comma", self._remove_trailing_commas(raw)),
            ("full_repair",            self._full_repair(raw)),
        ]

        for label, candidate in attempts:
            if candidate is None:
                continue
            result = self._try_parse(candidate)
            if result is not None:
                repaired = label != "raw"
                if repaired:
                    logger.info(f"[DebugAgent] JSON fixed via: {label}")
                return result, repaired

        logger.error("[DebugAgent] All JSON repair strategies failed.")
        return None, False

    def fix_test_plan(
        self, raw_response: str, instruction: str = ""
    ) -> Tuple[Optional[Dict], bool]:
        plan, was_repaired = self.fix_json_string(raw_response)
        if plan is None:
            return None, was_repaired
        if not isinstance(plan, dict):
            logger.error("[DebugAgent] Parsed JSON is not a dict.")
            return None, True

        if "steps" not in plan or not isinstance(plan.get("steps"), list):
            logger.warning("[DebugAgent] 'steps' missing — inserting empty list.")
            plan["steps"] = []
            was_repaired = True

        repaired_steps = []
        for idx, step in enumerate(plan["steps"]):
            if not isinstance(step, dict):
                logger.warning(f"[DebugAgent] Step {idx} not a dict — skipped.")
                was_repaired = True
                continue

            # Unknown action → safe default
            if step.get("action") not in VALID_ACTIONS:
                logger.warning(
                    f"[DebugAgent] Unknown action '{step.get('action')}' "
                    f"at step {idx} — defaulting to 'wait'"
                )
                step["action"] = "wait"
                was_repaired = True

            step, step_repaired = self._repair_step(step, idx, instruction)
            if step_repaired:
                was_repaired = True
            repaired_steps.append(step)

        plan["steps"] = repaired_steps
        plan, plan_repaired = self._validate_test_plan(plan)
        if plan_repaired:
            was_repaired = True

        # Final schema validation pass
        try:
            from step_schema import validate_and_repair_plan
            plan, issues = validate_and_repair_plan(plan, instruction=instruction)
            if issues:
                was_repaired = True
                plan["_validation_issues"] = issues
        except Exception as e:
            logger.warning(f"[DebugAgent] Schema validation skipped: {e}")

        return plan, was_repaired

    # ── Selector Repair ───────────────────────────────────────────────────────

    def fix_selector(self, selector: str, description: str = "", action: str = "") -> str:
        if selector and not self._is_bad_selector(selector):
            return selector
        fallback = self._guess_fallback_selector(description, action)
        if fallback:
            logger.warning(
                f"[DebugAgent] Bad selector '{selector}' → '{fallback}' "
                f"(hint: '{description}')"
            )
            return fallback
        logger.warning(f"[DebugAgent] Cannot fix selector '{selector}' — keeping as-is.")
        return selector or "body"

    def suggest_alternative_selector(
        self, failed_selector: str, description: str, action: str
    ) -> str:
        return self.fix_selector("", description, action)

    # ── JSON Internals ────────────────────────────────────────────────────────

    @staticmethod
    def _try_parse(text: str) -> Optional[Dict]:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _strip_markdown(text: str) -> str:
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text.strip())
        return text.strip()

    @staticmethod
    def _extract_json_block(text: str) -> Optional[str]:
        start = text.find("{")
        end   = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start:end + 1]

    @staticmethod
    def _fix_quotes(text: str) -> str:
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        return re.sub(r"(?<![\\])'", '"', text)

    @staticmethod
    def _remove_trailing_commas(text: str) -> str:
        return re.sub(r",\s*([\]}])", r"\1", text)

    def _full_repair(self, text: str) -> str:
        text = self._strip_markdown(text)
        extracted = self._extract_json_block(text)
        if extracted:
            text = extracted
        text = self._fix_quotes(text)
        text = self._remove_trailing_commas(text)
        return text

    # ── Selector Internals ────────────────────────────────────────────────────

    @staticmethod
    def _is_bad_selector(selector: str) -> bool:
        for pattern in _BAD_SELECTOR_PATTERNS:
            if re.match(pattern, selector, re.IGNORECASE):
                return True
        return False

    def _guess_fallback_selector(self, description: str, action: str) -> Optional[str]:
        combined = f"{(description or '').lower()} {(action or '').lower()}"

        keyword_map = [
            (["add to cart", "cart", "buy"],                        "cart"),
            (["image tab", "images tab", "click images"],           "images_tab"),
            (["search box", "search input", "search field",
              "type", "fill", "enter", "query", "text box"],        "search"),
            (["search button", "submit", "press enter", "go"],      "submit"),
            (["image", "photo", "picture", "download image"],       "image"),
            (["download", "save", "export"],                        "download"),
            (["link", "anchor", "href"],                            "link"),
            (["button", "click"],                                   "button"),
            (["youtube search", "search youtube"],                  "youtube_search"),
            (["play video", "first video", "watch video"],          "youtube_video"),
            (["first product", "click product", "open product"],    "product"),
            (["username", "email", "user name"],                    "login_username"),
            (["password", "pass", "pwd"],                           "login_password"),
            (["login button", "sign in button", "submit login"],    "login_button"),
        ]

        for keywords, pool_key in keyword_map:
            if any(kw in combined for kw in keywords):
                pool = SELECTOR_FALLBACKS.get(pool_key, [])
                if pool:
                    return pool[0]
        return None

    # ── Step Repair ───────────────────────────────────────────────────────────

    def _repair_step(
        self, step: Dict, idx: int, instruction: str = ""
    ) -> Tuple[Dict, bool]:
        repaired = False
        action = str(step.get("action", "wait")).lower().strip()
        step["action"] = action

        if not step.get("description"):
            step["description"] = f"Step {idx + 1}: {action}"
            repaired = True

        # ── Selector-required actions ──────────────────────────────────────
        if action in ("click", "fill", "assert", "hover", "select", "extract"):
            raw_sel = step.get("selector", "")
            fixed = self.fix_selector(raw_sel, step.get("description", ""), action)
            if fixed != raw_sel:
                step["selector"] = fixed
                repaired = True

        # ── navigate ──────────────────────────────────────────────────────
        if action == "navigate":
            url = step.get("url", "")
            if not url:
                step["url"] = _default_url()
                repaired = True
            elif not url.startswith(("http://", "https://")):
                step["url"] = f"https://{url}"
                repaired = True

        # ── fill ──────────────────────────────────────────────────────────
        elif action == "fill" and "value" not in step:
            step["value"] = ""
            repaired = True

        # ── press ─────────────────────────────────────────────────────────
        elif action == "press" and not step.get("key"):
            step["key"] = "Enter"
            repaired = True

        # ── wait ──────────────────────────────────────────────────────────
        elif action == "wait" and not step.get("duration"):
            step["duration"] = 2000
            repaired = True

        # ── scroll ────────────────────────────────────────────────────────
        elif action == "scroll":
            step.setdefault("direction", "down")
            step.setdefault("amount", 1000)

        # ── search / search_products (legacy) ─────────────────────────────
        elif action in ("search", "search_products"):
            if not step.get("query"):
                q = _extract_query(instruction)
                step["query"] = q or "laptop"
                repaired = True
            step.setdefault("platform", "amazon")

        # ── apply_sort ────────────────────────────────────────────────────
        elif action == "apply_sort":
            step.setdefault("sort_type", "rating")
            step.setdefault("platform", "amazon")

        # ── apply_price_filter ────────────────────────────────────────────
        elif action == "apply_price_filter":
            step.setdefault("max_price", 999999)
            step.setdefault("min_price", 0)
            step.setdefault("platform", "amazon")

        # ── apply_rating_filter ───────────────────────────────────────────
        elif action == "apply_rating_filter":
            step.setdefault("min_rating", 4.0)
            step.setdefault("platform", "amazon")

        # ── click_product_index ───────────────────────────────────────────
        elif action == "click_product_index":
            step.setdefault("index", 1)
            step.setdefault("platform", "amazon")

        # ── click_product_name ────────────────────────────────────────────
        elif action == "click_product_name":
            if not step.get("product_name"):
                step["product_name"] = _extract_query(instruction) or "product"
                repaired = True
            step.setdefault("platform", "amazon")

        # ── select_variant ────────────────────────────────────────────────
        elif action == "select_variant":
            if not step.get("variant"):
                step["variant"] = ""
                repaired = True
            step.setdefault("platform", "amazon")

        # ── select_quantity ───────────────────────────────────────────────
        elif action == "select_quantity":
            step.setdefault("quantity", 1)
            step.setdefault("platform", "amazon")

        # ── add_to_cart / buy_now ─────────────────────────────────────────
        elif action in ("add_to_cart", "buy_now"):
            step.setdefault("platform", "amazon")
            step.setdefault("quantity", 1)

        # ── smart_find_and_add_best ───────────────────────────────────────
        elif action == "smart_find_and_add_best":
            step.setdefault("platform", "amazon")
            step.setdefault("min_rating", 0.0)
            step.setdefault("limit", 20)

        # ── search_images ─────────────────────────────────────────────────
        elif action == "search_images":
            if not step.get("query"):
                step["query"] = _extract_query(instruction) or "beautiful landscape"
                repaired = True

        # ── click_google_image ────────────────────────────────────────────
        elif action == "click_google_image":
            step.setdefault("index", 1)

        # ── download_highres ──────────────────────────────────────────────
        # no required fields

        # ── youtube_search ────────────────────────────────────────────────
        elif action == "youtube_search":
            if not step.get("query"):
                step["query"] = _extract_query(instruction) or "funny cats"
                repaired = True
            step.setdefault("skip_shorts", True)

        # ── youtube_interact ──────────────────────────────────────────────
        elif action == "youtube_interact":
            if not step.get("interaction"):
                desc = step.get("description", "").lower()
                if "like"        in desc: step["interaction"] = "like"
                elif "comment"   in desc: step["interaction"] = "open_comments"
                elif "scroll"    in desc: step["interaction"] = "scroll_comments"
                elif "fullscreen"in desc: step["interaction"] = "fullscreen"
                elif "subscribe" in desc: step["interaction"] = "subscribe"
                elif "settings"  in desc: step["interaction"] = "settings"
                elif "mute"      in desc: step["interaction"] = "mute"
                elif "pause"     in desc: step["interaction"] = "pause"
                else:                     step["interaction"] = "like"
                repaired = True

        # ── smart_login ───────────────────────────────────────────────────
        elif action == "smart_login":
            if not step.get("username"):
                step["username"] = "testuser"
                repaired = True
            if not step.get("password"):
                step["password"] = "password123"
                repaired = True

        # ── compare_flights ───────────────────────────────────────────────
        elif action == "compare_flights":
            step.setdefault("origin",      "DEL")
            step.setdefault("destination", "BOM")
            step.setdefault("date",        "tomorrow")

        # ── start_monitoring ──────────────────────────────────────────────
        elif action == "start_monitoring":
            if not step.get("monitors"):
                il = instruction.lower()
                if "ps5" in il or "product" in il:
                    monitor = {"type": "ecommerce", "id": "PS5",     "condition": "below",       "threshold": 45000, "action": "notify"}
                elif "tesla" in il or "stock" in il:
                    monitor = {"type": "stock",     "id": "TSLA",    "condition": "drops_percent","threshold": 5,     "action": "buy_now"}
                elif "bitcoin" in il or "btc" in il:
                    monitor = {"type": "crypto",    "id": "bitcoin", "condition": "below",       "threshold": 50000, "action": "notify"}
                else:
                    monitor = {"type": "crypto",    "id": "bitcoin", "condition": "below",       "threshold": 50000, "action": "notify"}
                step["monitors"] = [monitor]
                repaired = True

        # ── check_monitors / stop_monitoring ──────────────────────────────
        # no required fields

        # ── extract ───────────────────────────────────────────────────────
        elif action == "extract":
            step.setdefault("variable",  f"extracted_{idx + 1}")
            step.setdefault("attribute", "textContent")

        # ── request_human_input ───────────────────────────────────────────
        elif action == "request_human_input":
            step.setdefault("prompt", "Human input required")

        return step, repaired

    # ── Plan-level validation ─────────────────────────────────────────────────

    def _validate_test_plan(self, plan: Dict) -> Tuple[Dict, bool]:
        repaired = False

        # Monitoring-only plans don't need a leading navigate
        steps = plan.get("steps", [])
        is_monitoring = any(s.get("action") == "start_monitoring" for s in steps)

        if not steps:
            plan["steps"] = [{
                "action": "navigate",
                "url": _default_url(),
                "description": "Navigate to default page",
            }]
            return plan, True

        if not is_monitoring and steps[0].get("action") != "navigate":
            plan["steps"].insert(0, {
                "action": "navigate",
                "url": _default_url(),
                "description": "Navigate to default page",
            })
            repaired = True

        for step in plan["steps"]:
            if step.get("action") == "navigate":
                url = step.get("url", "")
                if not url:
                    step["url"] = _default_url()
                    repaired = True
                elif not url.startswith(("http://", "https://")):
                    step["url"] = f"https://{url}"
                    repaired = True

        return plan, repaired


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_url() -> str:
    try:
        import config as _cfg
        return getattr(_cfg, "DEFAULT_NAVIGATE_URL", "https://www.google.com")
    except Exception:
        return "https://www.google.com"


def _extract_query(instruction: str) -> str:
    try:
        from rag_store import extract_search_term
        return extract_search_term(instruction) or ""
    except Exception:
        return ""


# ── Singleton ─────────────────────────────────────────────────────────────────
debug_agent = DebugAgent()
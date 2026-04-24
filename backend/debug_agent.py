"""
Debug Agent Module — Production Upgrade
Fixes invalid JSON from LLM output and heals broken selectors.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


SELECTOR_FALLBACKS: Dict[str, list] = {
    "search": [
        "textarea[name='q']",
        "input[name='q']",
        "input[type='search']",
        "input[placeholder*='Search' i]",
        "[role='searchbox']",
        "input[aria-label*='search' i]",
        "textarea",
        "input[id='twotabsearchtextbox']",  # Amazon
    ],
    "submit": [
        "input[type='submit']",
        "button[type='submit']",
        "button[aria-label*='search' i]",
        "[role='button'][aria-label*='Search' i]",
        "input[value='Google Search']",
        "input[id='nav-search-submit-button']",  # Amazon
    ],
    "button": [
        "button",
        "input[type='button']",
        "[role='button']",
    ],
    "link": ["a[href]"],
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
    ],
}

_BAD_SELECTOR_PATTERNS = [
    r"^\s*$",
    r"^null$",
    r"^none$",
    r"^n/a$",
    r"^undefined$",
    r"^selector$",
    r"^\.\s*$",
    r"^#\s*$",
    r"^css selector$",
    r"^<.*>$",
]


class DebugAgent:

    # ------------------------------------------------------------------
    # JSON repair
    # ------------------------------------------------------------------

    def fix_json_string(self, raw: str) -> Tuple[Optional[Dict], bool]:
        if not raw or not raw.strip():
            logger.warning("[DebugAgent] Empty LLM response received.")
            return None, False

        attempts = [
            ("raw", raw),
            ("stripped_markdown", self._strip_markdown(raw)),
            ("extracted_block", self._extract_json_block(raw)),
            ("single_to_double_quotes", self._fix_quotes(raw)),
            ("trailing_commas_removed", self._remove_trailing_commas(raw)),
            ("full_repair", self._full_repair(raw)),
        ]

        for label, candidate in attempts:
            if candidate is None:
                continue
            result = self._try_parse(candidate)
            if result is not None:
                repaired = label != "raw"
                if repaired:
                    logger.info(f"[DebugAgent] JSON fixed via strategy: {label}")
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
            logger.warning("[DebugAgent] 'steps' key missing — inserting empty list.")
            plan["steps"] = []
            was_repaired = True

        repaired_steps = []
        for idx, step in enumerate(plan["steps"]):
            if not isinstance(step, dict):
                logger.warning(f"[DebugAgent] Step {idx} is not a dict, skipping.")
                was_repaired = True
                continue
            step, step_repaired = self._repair_step(step, idx)
            if step_repaired:
                was_repaired = True
            repaired_steps.append(step)

        plan["steps"] = repaired_steps
        plan, plan_repaired = self._validate_test_plan(plan)
        if plan_repaired:
            was_repaired = True

        # Final pass: schema-level validation + Google-Images flow enforcement.
        try:
            from step_schema import validate_and_repair_plan
            plan, issues = validate_and_repair_plan(plan, instruction=instruction)
            if issues:
                was_repaired = True
                plan["_validation_issues"] = issues
        except Exception as e:
            logger.warning(f"[DebugAgent] Schema validation skipped: {e}")

        return plan, was_repaired

    # ------------------------------------------------------------------
    # Selector repair
    # ------------------------------------------------------------------

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
        logger.warning(f"[DebugAgent] Could not fix selector '{selector}', keeping as-is.")
        return selector or "body"

    def suggest_alternative_selector(self, failed_selector: str, description: str, action: str) -> str:
        return self.fix_selector("", description, action)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

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
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start: end + 1]

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

    @staticmethod
    def _is_bad_selector(selector: str) -> bool:
        for pattern in _BAD_SELECTOR_PATTERNS:
            if re.match(pattern, selector, re.IGNORECASE):
                return True
        return False

    def _guess_fallback_selector(self, description: str, action: str) -> Optional[str]:
        desc_lower = (description or "").lower()
        action_lower = (action or "").lower()
        combined = f"{desc_lower} {action_lower}"

        keyword_map = [
            (["add to cart", "cart", "buy"], "cart"),
            (["image tab", "images tab", "click images", "images link"], "images_tab"),
            (["search box", "search input", "search field", "type", "fill",
              "enter", "query", "text box"], "search"),
            (["search button", "submit", "press enter", "go"], "submit"),
            (["image", "photo", "picture", "download image"], "image"),
            (["download", "save", "export"], "download"),
            (["link", "anchor", "href"], "link"),
            (["button", "click"], "button"),
        ]

        for keywords, pool_key in keyword_map:
            if any(kw in combined for kw in keywords):
                pool = SELECTOR_FALLBACKS.get(pool_key, [])
                if pool:
                    return pool[0]
        return None

    def _repair_step(self, step: Dict, idx: int) -> Tuple[Dict, bool]:
        repaired = False
        action = str(step.get("action", "wait")).lower().strip()
        step["action"] = action

        if not step.get("description"):
            step["description"] = f"Step {idx + 1}: {action}"
            repaired = True

        if action in ("click", "fill", "assert", "hover", "select", "extract"):
            raw_selector = step.get("selector", "")
            fixed = self.fix_selector(raw_selector, step.get("description", ""), action)
            if fixed != raw_selector:
                step["selector"] = fixed
                repaired = True

        if action == "fill" and "value" not in step:
            step["value"] = ""
            repaired = True

        if action == "navigate":
            url = step.get("url", "")
            if not url:
                step["url"] = config_default_url()
                repaired = True
            elif not url.startswith(("http://", "https://")):
                step["url"] = f"https://{url}"
                repaired = True

        if action == "press" and not step.get("key"):
            step["key"] = "Enter"
            repaired = True

        if action == "wait" and not step.get("duration"):
            step["duration"] = 2000
            repaired = True

        return step, repaired

    def _validate_test_plan(self, plan: Dict) -> Tuple[Dict, bool]:
        repaired = False

        if not plan.get("steps"):
            plan["steps"] = [{
                "action": "navigate",
                "url": config_default_url(),
                "description": "Navigate to default page",
            }]
            repaired = True

        if plan["steps"] and plan["steps"][0].get("action") != "navigate":
            plan["steps"].insert(0, {
                "action": "navigate",
                "url": config_default_url(),
                "description": "Navigate to default page",
            })
            repaired = True

        for step in plan["steps"]:
            if step.get("action") == "navigate":
                url = step.get("url", "")
                if not url:
                    step["url"] = config_default_url()
                    repaired = True
                elif not url.startswith(("http://", "https://")):
                    step["url"] = f"https://{url}"
                    repaired = True

        return plan, repaired


def config_default_url() -> str:
    try:
        import config as _cfg
        return getattr(_cfg, "DEFAULT_NAVIGATE_URL", "https://www.google.com")
    except Exception:
        return "https://www.google.com"


# Singleton
debug_agent = DebugAgent()
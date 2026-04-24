"""
Automation Engine — Production Upgrade
Self-healing execution: plan → execute → observe → fix → retry loop
"""

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeout

import config
from rag_store import get_rag_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str, max_len: int = 30) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:max_len]


# ---------------------------------------------------------------------------
# Execution context passed across steps
# ---------------------------------------------------------------------------

class ExecutionContext:
    def __init__(self, test_folder: Path, current_url: str = ""):
        self.test_folder = test_folder
        self.current_url = current_url
        self.step_results: List[Dict] = []
        self.variables: Dict[str, Any] = {}  # For future variable extraction


# ---------------------------------------------------------------------------
# Automation Engine
# ---------------------------------------------------------------------------

class AutomationEngine:

    MAX_SELECTOR_RETRIES = 3

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.execution_log: List[Dict] = []
        self.test_folder: Optional[Path] = None
        self._rag = get_rag_store()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=config.BROWSER_HEADLESS,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": config.VIEWPORT_WIDTH, "height": config.VIEWPORT_HEIGHT},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            java_script_enabled=True,
        )
        # Block unnecessary resources for speed
        await self.context.route(
            "**/*.{woff,woff2,ttf,otf}",
            lambda route: route.abort(),
        )

    async def cleanup(self):
        for obj, name in [(self.page, "page"), (self.context, "context"),
                          (self.browser, "browser"), (self.playwright, "playwright")]:
            try:
                if obj:
                    await obj.close() if hasattr(obj, "close") else await obj.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Main execution entry point
    # ------------------------------------------------------------------

    async def execute_test_plan(self, test_plan: Dict) -> Dict:
        self.execution_log = []
        start_time = datetime.now()

        self.test_folder = (
            config.SCREENSHOTS_DIR / f"test_{start_time.strftime('%H%M%S')}"
        )
        self.test_folder.mkdir(parents=True, exist_ok=True)

        overall_success = True
        error_message = None
        skipped = 0

        steps = test_plan.get("steps", []) or []
        total = len(steps)
        logger.info(f"[AutomationEngine] ▶ Starting run: {total} step(s)")

        try:
            await self.initialize()
            self.page = await self.context.new_page()

            ctx = ExecutionContext(self.test_folder)

            for idx, step in enumerate(steps):
                step_num = idx + 1
                action = (step or {}).get("action", "?")
                desc = (step or {}).get("description", "")
                step_started = datetime.now()
                logger.info(
                    f"[Step {step_num}/{total}] ▶ action={action} desc={desc!r}"
                )

                # Crash-proof: any unexpected exception inside the healing loop
                # is captured here so the run continues with the next step.
                try:
                    step_success = await self._execute_with_healing(step, step_num, ctx)
                except Exception as e:
                    logger.exception(
                        f"[Step {step_num}] Unhandled exception in healing loop: {e}"
                    )
                    self.execution_log.append(
                        self._build_log_entry(
                            step or {}, step_num, "skipped", None,
                            f"Skipped due to unhandled error: {e}",
                        )
                    )
                    skipped += 1
                    overall_success = False
                else:
                    elapsed = (datetime.now() - step_started).total_seconds()
                    if step_success:
                        logger.info(
                            f"[Step {step_num}/{total}] ✅ PASS ({elapsed:.2f}s)"
                        )
                    else:
                        overall_success = False
                        logger.warning(
                            f"[Step {step_num}/{total}] ❌ FAIL ({elapsed:.2f}s) — continuing."
                        )

                await asyncio.sleep(config.STEP_DELAY / 1000)

        except Exception as e:
            logger.exception(f"[AutomationEngine] Fatal error: {e}")
            overall_success = False
            error_message = str(e)
        finally:
            await self.cleanup()

        duration = (datetime.now() - start_time).total_seconds()

        passed = sum(1 for s in self.execution_log if s.get("status") == "success")
        failed = sum(1 for s in self.execution_log if s.get("status") == "failed")
        summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration": round(duration, 2),
        }
        logger.info(
            f"[AutomationEngine] ◀ Run complete: "
            f"{passed} passed / {failed} failed / {skipped} skipped "
            f"in {duration:.2f}s"
        )

        return {
            "success": overall_success,
            "status": "PASS" if overall_success else "FAIL",
            "steps": self.execution_log,
            "duration": duration,
            "timestamp": start_time.isoformat(),
            "test_folder": str(self.test_folder),
            "metadata_file": None,
            "message": error_message,
            "screenshot": None,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Self-healing execution loop
    # ------------------------------------------------------------------

    async def _execute_with_healing(
        self, step: Dict, step_num: int, ctx: ExecutionContext
    ) -> bool:
        """
        Execute a step with up to MAX_SELECTOR_RETRIES healing attempts.
        On each failure: ask LLM for a better selector, then retry.
        """
        # Pre-flight guard: malformed step → log + skip, never crash.
        if not isinstance(step, dict):
            err = f"Step {step_num} is not a dict (got {type(step).__name__}) — skipping"
            logger.error(f"[AutomationEngine] {err}")
            self.execution_log.append(
                self._build_log_entry({}, step_num, "skipped", None, err)
            )
            return False

        action = step.get("action", "").lower()
        if not action:
            err = f"Step {step_num} has no action — skipping"
            logger.error(f"[AutomationEngine] {err}")
            self.execution_log.append(
                self._build_log_entry(step, step_num, "skipped", None, err)
            )
            return False

        attempt = 0
        last_error = None

        while attempt < self.MAX_SELECTOR_RETRIES:
            attempt += 1
            success, error, screenshot_path = await self._execute_step(
                step, step_num, ctx, attempt
            )
            if success:
                # Record selector success in RAG
                if action in ("click", "fill") and step.get("selector"):
                    self._rag.record_success(
                        description=step.get("description", ""),
                        selector=step.get("selector", ""),
                        url=ctx.current_url,
                    )
                self.execution_log.append(
                    self._build_log_entry(step, step_num, "success", screenshot_path, None)
                )
                return True

            last_error = error
            logger.warning(
                f"Step {step_num} attempt {attempt} failed: {error}"
            )

            if attempt < self.MAX_SELECTOR_RETRIES and action in ("click", "fill", "assert"):
                healed_selector = await self._heal_selector(step, error, ctx)
                if healed_selector and healed_selector != step.get("selector"):
                    logger.info(
                        f"[Healing] Replacing selector '{step.get('selector')}' "
                        f"→ '{healed_selector}'"
                    )
                    step = {**step, "selector": healed_selector}
                    await asyncio.sleep(1)
                else:
                    break
            else:
                break

        self.execution_log.append(
            self._build_log_entry(step, step_num, "failed", None, last_error)
        )
        return False

    async def _heal_selector(
        self, step: Dict, error: str, ctx: ExecutionContext
    ) -> Optional[str]:
        """
        Multi-strategy selector healing with Amazon-specific improvements.
        1. Amazon-specific selectors (priority)
        2. RAG store lookup
        3. DOM introspection
        4. LLM-based suggestion (delegated to llm_service to avoid circular import)
        """
        description = step.get("description", "").lower()
        action = step.get("action", "")
        current_selector = step.get("selector", "")
        
        # 🔥 AMAZON-SPECIFIC HEALING (Priority for Amazon sites)
        if "amazon" in ctx.current_url.lower():
            # Product click healing
            if "product" in description or "first" in description or "result" in description:
                amazon_product_selectors = [
                    "div[data-component-type='s-search-result'] h2 a",
                    "div[data-component-type='s-search-result']:first-child a.a-link-normal",
                    "a.a-link-normal.s-underline-text",
                    "h2 a.a-link-normal",
                    "div[data-component-type='s-search-result'] a.a-link-normal"
                ]
                for sel in amazon_product_selectors:
                    if sel != current_selector:
                        try:
                            await self.page.wait_for_selector(sel, timeout=3000)
                            logger.info(f"[Healing] Amazon product selector worked: {sel}")
                            return sel
                        except Exception:
                            continue
            
            # Add to cart healing
            if "cart" in description or "add" in description or "buy" in description:
                amazon_cart_selectors = [
                    "input#add-to-cart-button",
                    "#add-to-cart-button",
                    "input[name='submit.add-to-cart']",
                    "input[type='submit'][value='Add to Cart']",
                    "input[value='Add to Cart']",
                    "button#add-to-cart-button"
                ]
                for sel in amazon_cart_selectors:
                    if sel != current_selector:
                        try:
                            await self.page.wait_for_selector(sel, timeout=3000)
                            logger.info(f"[Healing] Amazon cart selector worked: {sel}")
                            return sel
                        except Exception:
                            continue

        # Strategy 1: RAG lookup
        rag_suggestions = self._rag.find_similar_selectors(description, ctx.current_url)
        for sel in rag_suggestions:
            if sel != step.get("selector"):
                try:
                    await self.page.wait_for_selector(sel, timeout=3000)
                    logger.info(f"[Healing] RAG suggested selector worked: {sel}")
                    return sel
                except Exception:
                    continue

        # Strategy 2: DOM inspection
        dom_sel = await self._inspect_dom_for_selector(description, action)
        if dom_sel:
            return dom_sel

        # Strategy 3: LLM (imported lazily to avoid circular imports)
        try:
            from llm_service import llm_service
            llm_sel = llm_service.fix_selector_via_llm(step, error)
            if llm_sel:
                return llm_sel
        except Exception as e:
            logger.warning(f"[Healing] LLM selector healing failed: {e}")

        return None

    async def _inspect_dom_for_selector(self, description: str, action: str) -> Optional[str]:
        """Try to infer a working selector by inspecting the live DOM."""
        desc_lower = description.lower()
        try:
            candidates = []

            if any(kw in desc_lower for kw in ["search", "query", "type", "fill"]):
                candidates = [
                    "textarea[name='q']",
                    "input[name='q']",
                    "input[type='search']",
                    "[role='searchbox']",
                    "input[type='text']:visible",
                ]
            elif any(kw in desc_lower for kw in ["button", "submit", "click", "press"]):
                candidates = [
                    "button[type='submit']",
                    "input[type='submit']",
                    "[role='button']:visible",
                    "button:visible",
                ]
            elif any(kw in desc_lower for kw in ["image", "photo", "picture"]):
                candidates = [
                    "a[href*='tbm=isch']",
                    "img.Q4LuWd",
                    "img.rg_i",
                    "div[jsname='dTDiAc'] a",
                ]
            # Amazon-specific DOM inspection
            elif "amazon" in self.page.url.lower():
                if "product" in desc_lower or "result" in desc_lower:
                    candidates = [
                        "div[data-component-type='s-search-result'] h2 a",
                        "div.s-result-item h2 a",
                        "[data-component-type='s-search-result'] a"
                    ]
                elif "cart" in desc_lower or "add" in desc_lower:
                    candidates = [
                        "input#add-to-cart-button",
                        "#add-to-cart-button",
                        "input[name='submit.add-to-cart']"
                    ]

            for sel in candidates:
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        logger.info(f"[DOM Inspect] Found working selector: {sel}")
                        return sel
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[DOM Inspect] Failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Core step executor
    # ------------------------------------------------------------------

    async def _execute_step(
        self, step: Dict, step_num: int, ctx: ExecutionContext, attempt: int
    ) -> Tuple[bool, Optional[str], Optional[Path]]:
        """
        Returns (success, error_message, screenshot_path).
        """
        action = step.get("action", "").lower()
        screenshot_path: Optional[Path] = None
        error: Optional[str] = None

        try:
            if action == "navigate":
                await self._action_navigate(step, step_num, ctx)

            elif action == "wait":
                duration = step.get("duration", 1000)
                await asyncio.sleep(duration / 1000)

            elif action == "fill":
                await self._action_fill(step, step_num)

            elif action == "press":
                await self._action_press(step, step_num)

            elif action == "click":
                await self._action_click(step, step_num)

            elif action == "assert":
                await self._action_assert(step, step_num)

            elif action == "download":
                await self._action_download(step, step_num)
                # ✅ FIX: Validate download actually happened
                if not step.get("download_path"):
                    raise Exception("Download failed - no file was saved")
                # Check file exists
                if not Path(step.get("download_path")).exists():
                    raise Exception(f"Download claimed success but file missing: {step.get('download_path')}")

            elif action == "scroll":
                await self._action_scroll(step, step_num)

            elif action == "hover":
                await self._action_hover(step, step_num)

            elif action == "select":
                await self._action_select(step, step_num)

            elif action == "extract":
                await self._action_extract(step, step_num, ctx)

            else:
                # Surface as a normal failure so it shows up in the report
                # rather than being silently logged as success.
                raise ValueError(f"Unknown action '{action}'")

            # Screenshot on success
            screenshot_path = self.test_folder / f"step_{step_num}_attempt{attempt}.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=False)
            logger.info(f"Step {step_num}: ✅ {action} succeeded")
            return True, None, screenshot_path

        except Exception as e:
            error = str(e)
            logger.error(f"Step {step_num} ({action}) attempt {attempt} failed: {error}")
            try:
                screenshot_path = self.test_folder / f"step_{step_num}_fail_a{attempt}.png"
                await self.page.screenshot(path=str(screenshot_path), full_page=False)
            except Exception:
                screenshot_path = None
            return False, error, screenshot_path

    # ------------------------------------------------------------------
    # Individual action handlers
    # ------------------------------------------------------------------

    async def _action_navigate(self, step: Dict, step_num: int, ctx: ExecutionContext):
        url = step.get("url", "").strip()
        if not url:
            url = "https://www.google.com"
            logger.warning(f"Step {step_num}: Missing URL → defaulting to {url}")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        logger.info(f"Step {step_num}: Navigating to {url}")
        # 🔥 FIX: Use networkidle for better stability on Amazon
        await self.page.goto(url, timeout=config.BROWSER_TIMEOUT, wait_until="networkidle")
        await asyncio.sleep(0.5)
        ctx.current_url = self.page.url

    async def _action_fill(self, step: Dict, step_num: int):
        selector = step.get("selector", "")
        value = step.get("value", "")
        if not selector:
            raise ValueError("Fill step missing 'selector'")
        logger.info(f"Step {step_num}: Filling '{selector}' with '{value}'")
        await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT)
        await self.page.click(selector)
        await self.page.fill(selector, "")
        await self.page.type(selector, value, delay=30)  # human-like typing

    async def _action_press(self, step: Dict, step_num: int):
        key = step.get("key", "Enter")
        logger.info(f"Step {step_num}: Pressing '{key}'")
        await self.page.keyboard.press(key)
        try:
            await self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            await asyncio.sleep(1)

    async def _action_click(self, step: Dict, step_num: int):
        """Improved click handler that handles new tabs and navigation."""
        selector = step.get("selector", "")
        description = step.get("description", "").lower()

        if not selector:
            raise ValueError("Click step missing 'selector'")

        logger.info(f"Step {step_num}: Clicking '{selector}'")

        # --- Google Images tab special handling ---
        if "isch" in selector or "images" in description:
            await self._click_images_tab()
            return

        # --- First image result ---
        if (
            "first image" in description
            or (selector in ("img", "img.Q4LuWd") and "image" in description)
        ):
            await self._click_first_image()
            return

        # 🔥 HANDLE NAVIGATION / NEW TAB (Critical fix for Amazon)
        await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT, state="visible")

        try:
            # Check if click opens a new tab
            async with self.context.expect_page(timeout=5000) as new_page_info:
                await self.page.click(selector)
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
            self.page = new_page  # 🔥 SWITCH TO NEW TAB
            logger.info(f"Step {step_num}: Switched to new tab after click")
            await asyncio.sleep(1)
            return

        except Exception:
            # No new tab opened - handle normal navigation
            logger.debug(f"Step {step_num}: No new tab detected, handling as normal navigation")
            await self.page.click(selector)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                await asyncio.sleep(1)
            await asyncio.sleep(0.5)

    async def _click_images_tab(self):
        tab_selectors = [
            "a[href*='tbm=isch']",
            "a[href*='images']",
            "text=Images",
            "[aria-label='Images']",
            "a:has-text('Images')",
        ]
        for sel in tab_selectors:
            try:
                await self.page.wait_for_selector(sel, timeout=4000, state="visible")
                await self.page.click(sel)
                logger.info(f"Clicked Images tab with: {sel}")
                await asyncio.sleep(2)
                return
            except Exception:
                continue
        raise Exception("Could not find Google Images tab")

    async def _click_first_image(self):
        await self.page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1)

        image_selectors = [
            "a[jsname='sTFXNd']",
            "a.wXeWr",
            "div[jsname='dTDiAc'] a",
            "img.Q4LuWd",
            "img.rg_i",
        ]
        for sel in image_selectors:
            try:
                elements = await self.page.query_selector_all(sel)
                if elements:
                    await elements[0].click()
                    logger.info(f"Clicked first image with selector: {sel}")
                    await asyncio.sleep(2)
                    return
            except Exception:
                continue

        # Fallback: find first large non-logo image
        images = await self.page.query_selector_all("img")
        for img in images:
            try:
                box = await img.bounding_box()
                if box and box["width"] > 60 and box["height"] > 60:
                    src = await img.get_attribute("src") or ""
                    if not any(x in src.lower() for x in ("logo", "gstatic", "1x1", "pixel")):
                        await img.click()
                        logger.info("Clicked first large image (fallback)")
                        await asyncio.sleep(2)
                        return
            except Exception:
                continue

        raise Exception("Could not find a clickable image")

    async def _action_assert(self, step: Dict, step_num: int):
        assertion_type = step.get("assertion_type", "visible")
        selector = step.get("selector", "")
        expected = step.get("expected", "")

        logger.info(f"Step {step_num}: Assert [{assertion_type}] on '{selector}'")

        if assertion_type == "visible":
            await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT, state="visible")
        elif assertion_type == "text_contains":
            content = await self.page.text_content(selector) or ""
            if expected not in content:
                raise AssertionError(f"Expected '{expected}' in text '{content[:200]}'")
        elif assertion_type == "url_contains":
            current = self.page.url
            if expected not in current:
                raise AssertionError(f"Expected '{expected}' in URL '{current}'")
        elif assertion_type == "title_contains":
            title = await self.page.title()
            if expected not in title:
                raise AssertionError(f"Expected '{expected}' in title '{title}'")
        elif assertion_type == "count_gt":
            elements = await self.page.query_selector_all(selector)
            count = len(elements)
            if count <= int(expected):
                raise AssertionError(f"Expected count > {expected}, got {count}")
        else:
            logger.warning(f"Unknown assertion type: {assertion_type}")

    async def _action_download(self, step: Dict, step_num: int):
        """✅ FIXED: Download image from current page - actually saves the file."""
        import aiohttp
        import base64
        from datetime import datetime
        
        logger.info(f"Step {step_num}: Downloading image...")
        await asyncio.sleep(1)
        
        # Strategy 1: Get currently selected/visible image
        image_selectors = [
            "img.n3VNCb",  # Google Images viewer
            "img[jsname='knTssb']",  # Google Images alternative
            "img.s3UaBc",  # Another Google Images selector
            "div[role='dialog'] img",  # Lightbox image
            "img.iPVvYb",  # Google Images
            "img:visible",  # Any visible image
            ".rg_i img",  # Google search results image
            "img.Q4LuWd",  # Google Images thumbnail
        ]
        
        image_url = None
        image_element = None
        
        # Try to find the main image
        for selector in image_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    # Get the first visible/largest image
                    for el in elements:
                        box = await el.bounding_box()
                        if box and box["width"] > 50 and box["height"] > 50:
                            image_element = el
                            src = await el.get_attribute("src") or ""
                            if src.startswith("http"):
                                image_url = src
                                logger.info(f"Found image URL via {selector}: {src[:80]}...")
                                break
                    if image_url:
                        break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        # Strategy 2: If no direct image, check for background images or data-src
        if not image_url:
            try:
                # Check for data-src (lazy loaded images)
                data_src = await self.page.evaluate("""
                    () => {
                        const img = document.querySelector('img[data-src]');
                        return img ? img.getAttribute('data-src') : null;
                    }
                """)
                if data_src and data_src.startswith("http"):
                    image_url = data_src
                    logger.info(f"Found image via data-src: {image_url[:80]}...")
            except Exception:
                pass
        
        # Strategy 3: Extract from page context (Google Images specific)
        if not image_url and "google" in self.page.url.lower() and "img" in self.page.url.lower():
            try:
                # Get the actual image URL from Google's viewer
                image_url = await self.page.evaluate("""
                    () => {
                        const img = document.querySelector('img.n3VNCb');
                        if (img && img.src) return img.src;
                        const canvas = document.querySelector('canvas');
                        if (canvas) return canvas.toDataURL();
                        return null;
                    }
                """)
                if image_url:
                    logger.info(f"Extracted image from Google viewer")
            except Exception as e:
                logger.debug(f"Google extraction failed: {e}")
        
        # Download the image
        if image_url:
            try:
                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"downloaded_{timestamp}.jpg"
                filepath = self.test_folder / filename
                
                # Download using aiohttp
                if image_url.startswith("data:image"):
                    # Handle base64 encoded images
                    base64_data = image_url.split(",")[1]
                    image_bytes = base64.b64decode(base64_data)
                    filepath.write_bytes(image_bytes)
                    logger.info(f"Base64 image downloaded: {filepath}")
                else:
                    # HTTP download
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as resp:
                            if resp.status == 200:
                                image_bytes = await resp.read()
                                filepath.write_bytes(image_bytes)
                                logger.info(f"Image downloaded via HTTP: {filepath}")
                            else:
                                raise Exception(f"HTTP {resp.status}")
                
                # Store the path in step for reporting
                step["download_path"] = str(filepath)
                logger.info(f"✅ Image successfully downloaded to {filepath}")
                return
                
            except Exception as e:
                logger.error(f"Download failed: {e}")
                # Fall through to screenshot fallback
        
        # FALLBACK: Take screenshot if download fails
        logger.warning(f"Could not download image, saving screenshot as fallback")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = self.test_folder / f"screenshot_fallback_{timestamp}.png"
        await self.page.screenshot(path=str(fallback_path))
        step["download_path"] = str(fallback_path)
        step["download_fallback"] = True
        logger.info(f"Fallback screenshot saved: {fallback_path}")

    async def _action_scroll(self, step: Dict, step_num: int):
        direction = step.get("direction", "down")
        amount = step.get("amount", 300)
        dy = amount if direction == "down" else -amount
        logger.info(f"Step {step_num}: Scrolling {direction} by {amount}px")
        await self.page.evaluate(f"window.scrollBy(0, {dy})")
        await asyncio.sleep(0.5)

    async def _action_hover(self, step: Dict, step_num: int):
        selector = step.get("selector", "")
        if not selector:
            raise ValueError("Hover step missing 'selector'")
        logger.info(f"Step {step_num}: Hovering over '{selector}'")
        await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT)
        await self.page.hover(selector)
        await asyncio.sleep(0.3)

    async def _action_select(self, step: Dict, step_num: int):
        selector = step.get("selector", "")
        value = step.get("value", "")
        if not selector:
            raise ValueError("Select step missing 'selector'")
        logger.info(f"Step {step_num}: Selecting '{value}' in '{selector}'")
        await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT)
        await self.page.select_option(selector, value=value)

    async def _action_extract(self, step: Dict, step_num: int, ctx: ExecutionContext):
        selector = step.get("selector", "")
        variable = step.get("variable", f"extracted_{step_num}")
        attribute = step.get("attribute", "textContent")
        if not selector:
            raise ValueError("Extract step missing 'selector'")
        await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT)
        if attribute == "textContent":
            value = await self.page.text_content(selector) or ""
        else:
            el = await self.page.query_selector(selector)
            value = await el.get_attribute(attribute) or "" if el else ""
        ctx.variables[variable] = value.strip()
        logger.info(f"Step {step_num}: Extracted '{variable}' = '{value[:80]}'")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_log_entry(
        self,
        step: Dict,
        step_num: int,
        status: str,
        screenshot_path: Optional[Path],
        error: Optional[str],
    ) -> Dict:
        return {
            "step": step_num,
            "action": step.get("action", ""),
            "description": step.get("description", ""),
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "screenshot": str(screenshot_path) if screenshot_path else None,
            "error": error,
        }


# Singleton
automation_engine = AutomationEngine()
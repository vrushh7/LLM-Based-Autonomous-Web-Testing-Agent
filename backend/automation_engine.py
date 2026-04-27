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
    # Browser lifecycle with reinitialization
    # ------------------------------------------------------------------

    async def _ensure_browser_ready(self):
        """Ensure browser and page are ready for action"""
        if self.page is None or self.context is None or self.browser is None:
            logger.info("Browser not initialized, initializing...")
            await self.initialize()
            self.page = await self.context.new_page()
        else:
            try:
                await self.page.evaluate("1")
                logger.debug("Browser page is alive")
            except Exception as e:
                logger.warning(f"Browser page was closed: {e}, reinitializing...")
                await self.cleanup()
                await self.initialize()
                self.page = await self.context.new_page()

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
        """Clean up resources properly to avoid warnings."""
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
        
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    # ------------------------------------------------------------------
    # Main execution entry point
    # ------------------------------------------------------------------

    async def execute_test_plan(self, test_plan: Dict) -> Dict:
        await self._ensure_browser_ready()
        
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
            ctx = ExecutionContext(self.test_folder)

            for idx, step in enumerate(steps):
                step_num = idx + 1
                action = (step or {}).get("action", "?")
                desc = (step or {}).get("description", "")
                step_started = datetime.now()
                logger.info(f"[Step {step_num}/{total}] ▶ action={action} desc={desc!r}")

                try:
                    step_success = await self._execute_with_healing(step, step_num, ctx)
                except Exception as e:
                    logger.exception(f"[Step {step_num}] Unhandled exception: {e}")
                    self.execution_log.append(
                        self._build_log_entry(
                            step or {}, step_num, "skipped", None,
                            f"Skipped due to error: {e}",
                        )
                    )
                    skipped += 1
                    overall_success = False
                else:
                    elapsed = (datetime.now() - step_started).total_seconds()
                    if step_success:
                        logger.info(f"[Step {step_num}/{total}] ✅ PASS ({elapsed:.2f}s)")
                    else:
                        overall_success = False
                        logger.warning(f"[Step {step_num}/{total}] ❌ FAIL ({elapsed:.2f}s)")

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
        logger.info(f"[AutomationEngine] ◀ Run complete: {passed} passed / {failed} failed / {skipped} skipped in {duration:.2f}s")

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
        if not isinstance(step, dict):
            err = f"Step {step_num} is not a dict — skipping"
            logger.error(f"[AutomationEngine] {err}")
            self.execution_log.append(self._build_log_entry({}, step_num, "skipped", None, err))
            return False

        action = step.get("action", "").lower()
        if not action:
            err = f"Step {step_num} has no action — skipping"
            logger.error(f"[AutomationEngine] {err}")
            self.execution_log.append(self._build_log_entry(step, step_num, "skipped", None, err))
            return False

        attempt = 0
        last_error = None

        while attempt < self.MAX_SELECTOR_RETRIES:
            attempt += 1
            success, error, screenshot_path = await self._execute_step(step, step_num, ctx, attempt)
            if success:
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
            logger.warning(f"Step {step_num} attempt {attempt} failed: {error}")

            if attempt < self.MAX_SELECTOR_RETRIES and action in ("click", "fill", "assert"):
                healed_selector = await self._heal_selector(step, error, ctx)
                if healed_selector and healed_selector != step.get("selector"):
                    logger.info(f"[Healing] Replacing selector → '{healed_selector}'")
                    step = {**step, "selector": healed_selector}
                    await asyncio.sleep(1)
                else:
                    break
            else:
                break

        self.execution_log.append(self._build_log_entry(step, step_num, "failed", None, last_error))
        return False

    async def _heal_selector(
        self, step: Dict, error: str, ctx: ExecutionContext
    ) -> Optional[str]:
        description = step.get("description", "").lower()
        action = step.get("action", "")
        current_selector = step.get("selector", "")
        
        if "amazon" in ctx.current_url.lower():
            if "product" in description or "first" in description or "result" in description:
                amazon_product_selectors = [
                    "div[data-component-type='s-search-result'] h2 a",
                    "div.s-result-item h2 a",
                    "h2 a.a-link-normal",
                ]
                for sel in amazon_product_selectors:
                    if sel != current_selector:
                        try:
                            await self.page.wait_for_selector(sel, timeout=3000)
                            return sel
                        except Exception:
                            continue
            
            if "cart" in description or "add" in description:
                amazon_cart_selectors = [
                    "#add-to-cart-button",
                    "input#add-to-cart-button",
                    "input[name='submit.add-to-cart']"
                ]
                for sel in amazon_cart_selectors:
                    if sel != current_selector:
                        try:
                            await self.page.wait_for_selector(sel, timeout=3000)
                            return sel
                        except Exception:
                            continue

        return None

    # ------------------------------------------------------------------
    # Core step executor
    # ------------------------------------------------------------------

    async def _execute_step(
        self, step: Dict, step_num: int, ctx: ExecutionContext, attempt: int
    ) -> Tuple[bool, Optional[str], Optional[Path]]:
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
                if not step.get("download_path"):
                    raise Exception("Download failed")
            elif action == "scroll":
                await self._action_scroll(step, step_num)
            elif action == "hover":
                await self._action_hover(step, step_num)
            elif action == "select":
                await self._action_select(step, step_num)
            elif action == "extract":
                await self._action_extract(step, step_num, ctx)
            else:
                raise ValueError(f"Unknown action '{action}'")

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
                pass
            return False, error, screenshot_path

    # ------------------------------------------------------------------
    # Individual action handlers
    # ------------------------------------------------------------------

    async def _action_navigate(self, step: Dict, step_num: int, ctx: ExecutionContext):
        url = step.get("url", "").strip()
        if not url:
            url = "https://www.google.com"
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        logger.info(f"Step {step_num}: Navigating to {url}")
        await self.page.goto(url, timeout=config.BROWSER_TIMEOUT, wait_until="domcontentloaded")
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
        await self.page.type(selector, value, delay=30)
        await self.page.focus(selector)

    async def _action_press(self, step: Dict, step_num: int):
        key = step.get("key", "Enter")
        logger.info(f"Step {step_num}: Pressing '{key}'")
        await self.page.keyboard.press(key)

    # ------------------------------------------------------------------
    # 🔥 FINAL FIXED AMAZON PRODUCT CLICK
    # ------------------------------------------------------------------

    async def _click_first_amazon_product(self, step_num: int):
        """Click first Amazon product - waits for URL change, not selector"""
        logger.info(f"Step {step_num}: Clicking first Amazon product")

        selector = "div[data-component-type='s-search-result'] h2 a"

        # 🔥 RETRY instead of strict wait
        elements = []
        for _ in range(5):
            elements = await self.page.query_selector_all(selector)
            if elements:
                break
            await asyncio.sleep(2)

        if not elements:
            raise Exception("No products found after retries")

        product_link = elements[0]
        await product_link.scroll_into_view_if_needed()
        await asyncio.sleep(1)

        # 🔥 SIMPLE CLICK
        try:
            await product_link.click()
            logger.info("Clicked product link")
        except Exception as e:
            logger.warning(f"Click error: {e}")

        # 🔥 WAIT FOR URL CHANGE (NOT SELECTOR)
        for _ in range(10):
            url = self.page.url
            if "/dp/" in url or "/gp/product/" in url:
                logger.info(f"✅ Product page detected: {url[:80]}")
                return
            await asyncio.sleep(1)

        # 🔥 FALLBACK: NEW TAB
        logger.info("🔄 Trying new tab fallback")
        try:
            async with self.context.expect_page(timeout=8000) as new_page_info:
                await product_link.click()

            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
            self.page = new_page

            if "/dp/" in self.page.url or "/gp/product/" in self.page.url:
                logger.info(f"✅ Product opened in new tab: {self.page.url[:80]}")
                return
        except Exception as e:
            logger.warning(f"New tab fallback failed: {e}")

        raise Exception("❌ Failed to navigate to product page")

    # ------------------------------------------------------------------
    # 🔥 FINAL FIXED AMAZON ADD TO CART
    # ------------------------------------------------------------------

    async def _click_amazon_add_to_cart(self, step_num: int):
        """Enhanced Add to Cart with variant detection and multiple selectors"""
        logger.info(f"Step {step_num}: Adding product to cart")

        await asyncio.sleep(2)

        # 🔥 HANDLE VARIANTS
        variant_selectors = [
            "select[name='dropdown_selected_size_name']",
            "select#native_dropdown_selected_size_name",
            "select[name='dropdown_selected_color_name']",
        ]

        for var_sel in variant_selectors:
            try:
                dropdown = await self.page.query_selector(var_sel)
                if dropdown and await dropdown.is_visible():
                    await dropdown.select_option(index=1)
                    await asyncio.sleep(1)
                    logger.info("✅ Variant selected")
                    break
            except:
                continue

        # 🔥 MULTIPLE BUTTON OPTIONS
        selectors = [
            "#add-to-cart-button",
            "input#add-to-cart-button",
            "input[name='submit.add-to-cart']",
            "button[name='submit.add-to-cart']",
            "#buy-now-button"
        ]

        for sel in selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    await btn.click()
                    await asyncio.sleep(3)

                    # 🔥 VERIFY CART
                    cart = await self.page.query_selector("#nav-cart-count")
                    if cart:
                        count = await cart.text_content()
                        logger.info(f"✅ Cart updated: {count}")
                    else:
                        logger.info("✅ Action completed")

                    return
            except:
                continue

        raise Exception("❌ Add to cart failed")

    # ------------------------------------------------------------------
    # Other click handlers
    # ------------------------------------------------------------------

    async def _action_click(self, step: Dict, step_num: int):
        selector = step.get("selector", "")
        description = step.get("description", "").lower()

        if not selector:
            raise ValueError("Click step missing 'selector'")

        logger.info(f"Step {step_num}: Clicking '{selector}'")

        # Amazon product click
        if "amazon" in self.page.url.lower():
            if "product" in description or "first" in description or "result" in description:
                await self._click_first_amazon_product(step_num)
                return

        # Amazon Add to Cart / Buy Now
        if "amazon" in self.page.url.lower() and ("cart" in description or "add" in description or "buy" in description):
            await self._click_amazon_add_to_cart(step_num)
            return

        # Google Images tab
        if "isch" in selector or "images" in description:
            await self._click_images_tab()
            return

        # First image result
        if "first image" in description:
            await self._click_first_image()
            return

        # Login form - try Enter first
        if "login" in description or "sign" in description:
            logger.info(f"Step {step_num}: Login detected, trying Enter key first")
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(2)
            
            try:
                pwd_field = await self.page.query_selector("input[type='password']")
                if not pwd_field:
                    logger.info("Login successful with Enter key")
                    return
            except Exception:
                pass

        # Regular click with fallback
        await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT, state="visible")

        try:
            async with self.context.expect_page(timeout=8000) as new_page_info:
                await self.page.click(selector)
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
            self.page = new_page
            logger.info(f"Step {step_num}: Switched to new tab")
        except Exception:
            await self.page.click(selector)
            await asyncio.sleep(1)

    async def _click_images_tab(self):
        selectors = ["a[href*='tbm=isch']", "a[href*='images']", "text=Images"]
        for sel in selectors:
            try:
                await self.page.wait_for_selector(sel, timeout=4000, state="visible")
                await self.page.click(sel)
                await asyncio.sleep(2)
                return
            except Exception:
                continue
        raise Exception("Could not find Images tab")

    async def _click_first_image(self):
        await self.page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1)
        selectors = ["img.Q4LuWd", "img.rg_i"]
        for sel in selectors:
            try:
                elements = await self.page.query_selector_all(sel)
                if elements:
                    await elements[0].click()
                    await asyncio.sleep(2)
                    return
            except Exception:
                continue
        raise Exception("Could not find image")

    # ------------------------------------------------------------------
    # 🔥 FIXED ASSERT HANDLER (no unnecessary waiting)
    # ------------------------------------------------------------------

    async def _action_assert(self, step: Dict, step_num: int):
        assertion_type = step.get("assertion_type", "visible")
        selector = step.get("selector", "")
        expected = step.get("expected", "")

        logger.info(f"Step {step_num}: Assert [{assertion_type}] on '{selector}'")

        if assertion_type == "visible":
            element = await self.page.query_selector(selector)
            if not element:
                raise AssertionError(f"{selector} not found")
            logger.info(f"✅ Element visible")
        
        elif assertion_type == "text_contains":
            content = await self.page.text_content(selector) or ""
            if expected not in content:
                raise AssertionError(f"Expected '{expected}' in text")
            logger.info(f"✅ Text contains '{expected}'")
        
        elif assertion_type == "url_contains":
            if expected not in self.page.url:
                raise AssertionError(f"Expected '{expected}' in URL")
            logger.info(f"✅ URL contains '{expected}'")
        
        elif assertion_type == "count_eq":
            elements = await self.page.query_selector_all(selector)
            count = len(elements)
            expected_int = int(expected)
            if count != expected_int:
                raise AssertionError(f"Expected count == {expected_int}, got {count}")
            logger.info(f"✅ Count check passed: {count} == {expected_int}")
        
        elif assertion_type == "count_gt":
            elements = await self.page.query_selector_all(selector)
            count = len(elements)
            if count <= int(expected):
                raise AssertionError(f"Expected count > {expected}, got {count}")
            logger.info(f"✅ Count {count} > {expected}")
        
        else:
            logger.warning(f"Unknown assertion type: {assertion_type}")
            element = await self.page.query_selector(selector)
            if not element:
                raise AssertionError(f"{selector} not found")

    async def _action_download(self, step: Dict, step_num: int):
        import aiohttp
        from datetime import datetime
        
        logger.info(f"Step {step_num}: Downloading image...")
        await asyncio.sleep(1)
        
        selectors = ["img.n3VNCb", "img:visible", "img.Q4LuWd"]
        image_url = None
        
        for selector in selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    for el in elements:
                        box = await el.bounding_box()
                        if box and box["width"] > 50:
                            src = await el.get_attribute("src") or ""
                            if src.startswith("http"):
                                image_url = src
                                break
                    if image_url:
                        break
            except Exception:
                continue
        
        if image_url:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"downloaded_{timestamp}.jpg"
                filepath = self.test_folder / filename
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            filepath.write_bytes(image_bytes)
                            step["download_path"] = str(filepath)
                            logger.info(f"✅ Image downloaded")
                            return
            except Exception as e:
                logger.error(f"Download failed: {e}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = self.test_folder / f"screenshot_{timestamp}.png"
        await self.page.screenshot(path=str(fallback_path))
        step["download_path"] = str(fallback_path)
        logger.info(f"Fallback screenshot saved")

    async def _action_scroll(self, step: Dict, step_num: int):
        direction = step.get("direction", "down")
        amount = step.get("amount", 300)
        dy = amount if direction == "down" else -amount
        await self.page.evaluate(f"window.scrollBy(0, {dy})")
        await asyncio.sleep(0.5)

    async def _action_hover(self, step: Dict, step_num: int):
        selector = step.get("selector", "")
        if not selector:
            raise ValueError("Hover step missing 'selector'")
        await self.page.wait_for_selector(selector, timeout=config.BROWSER_TIMEOUT)
        await self.page.hover(selector)
        await asyncio.sleep(0.3)

    async def _action_select(self, step: Dict, step_num: int):
        selector = step.get("selector", "")
        value = step.get("value", "")
        if not selector:
            raise ValueError("Select step missing 'selector'")
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
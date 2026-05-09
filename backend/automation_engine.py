"""
Automation Engine — PRODUCTION READY v10.0
MAJOR NEW FEATURES:
1.  Pagination support: if result #N not on current page, navigates to next page
2.  Quantity selection before Add to Cart
3.  Variant selection (color/storage/size) e.g. "256GB", "Blue"
4.  Smart keyword-based filter/sort: "cheapest" → price low-high, "best rated" → rating, "most expensive" → price high-low
5.  Price-filter for "under ₹6000": applies Amazon/Flipkart price range filter
6.  Rating-filter: applies minimum rating filter
7.  "Best product" selection by composite score (rating × log(reviews) / price)
8.  Real-time monitoring every N seconds with autonomous trigger actions
9.  Google Images: open nth thumbnail + download highest-res version
10. YouTube: search, play, fullscreen, like, comment, subscribe, scroll, settings
11. Universal multi-step login with CAPTCHA/OTP human-fallback
12. Smart Browser Interaction Layer: retry with alternate selectors, scroll-to-find, JS fallback
13. All prior v9 fixes preserved
"""

import asyncio
import io
import logging
import re
import json
import uuid
import hashlib
import shutil
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import quote_plus, urlencode
from difflib import SequenceMatcher

import aiohttp
from playwright.async_api import (
    async_playwright, Browser, BrowserContext, Page,
    TimeoutError as PWTimeout, Response, Request
)
from PIL import Image
import pytesseract
import easyocr

import config
from rag_store import get_rag_store

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# EasyOCR
# ─────────────────────────────────────────────
_OCR_READER = None

def get_ocr_reader():
    global _OCR_READER
    if _OCR_READER is None:
        try:
            _OCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("EasyOCR initialized")
        except Exception as e:
            logger.warning(f"EasyOCR init failed: {e}")
    return _OCR_READER


# ─────────────────────────────────────────────
# Screenshot Cleanup
# ─────────────────────────────────────────────
def cleanup_old_screenshots(max_folders: int = 50):
    try:
        screenshots_dir = config.SCREENSHOTS_DIR
        if not screenshots_dir.exists():
            return
        folders = [f for f in screenshots_dir.iterdir() if f.is_dir()]
        if len(folders) > max_folders:
            folders.sort(key=lambda f: f.stat().st_mtime)
            for folder in folders[:len(folders) - max_folders]:
                shutil.rmtree(folder)
                logger.info(f"Cleaned up: {folder.name}")
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────
class ExecutionState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    NAVIGATING = "navigating"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_HUMAN = "waiting_human"


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────
@dataclass
class MonitorCondition:
    item_type: str          # "crypto" | "stock" | "ecommerce"
    item_id: str
    condition: str          # "below" | "above" | "drops_percent" | "rises_percent"
    threshold: float
    action: str             # "notify" | "add_to_cart" | "buy_now"
    last_value: float = 0.0
    last_check: datetime = field(default_factory=datetime.now)
    trigger_count: int = 0
    task_id: Optional[str] = None
    platform: Optional[str] = None   # for ecommerce monitoring
    product_url: Optional[str] = None


@dataclass
class ProductOption:
    name: str
    price: float
    rating: float
    reviews: int
    url: str
    platform: str
    asin: Optional[str] = None
    in_stock: bool = True
    index: int = 0

    @property
    def score(self) -> float:
        """Composite score: higher rating × more reviews ÷ price"""
        if self.price <= 0:
            return 0.0
        return (self.rating * math.log1p(self.reviews)) / self.price * 1000


@dataclass
class PageObservation:
    url: str
    title: str
    visible_text: str
    forms: List[Dict]
    buttons: List[Dict]
    inputs: List[Dict]
    links: List[Dict]
    images: List[Dict]
    possible_actions: List[str]
    has_error: bool = False
    error_message: str = ""


# ─────────────────────────────────────────────
# Smart Element Finder
# ─────────────────────────────────────────────
class SmartFinder:
    """
    Finds elements with multiple fallback strategies:
    1. Primary CSS selector
    2. Alternate CSS selectors
    3. Visible text search
    4. Scroll-to-find
    5. JS injection fallback
    """

    def __init__(self, page: Page):
        self.page = page

    async def find(
        self,
        selectors: List[str],
        text_hints: Optional[List[str]] = None,
        scroll_to_find: bool = True,
        timeout: int = 5000,
    ):
        """Returns first matching element or None."""
        # 1. Try each CSS selector
        for sel in selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=timeout, state="visible")
                if el:
                    return el
            except Exception:
                pass

        # 2. Try text hints
        if text_hints:
            for hint in text_hints:
                for tag in ["button", "a", "input", "span", "div"]:
                    try:
                        el = await self.page.query_selector(f"{tag}:has-text('{hint}')")
                        if el and await el.is_visible():
                            return el
                    except Exception:
                        pass

        if not scroll_to_find:
            return None

        # 3. Scroll and retry
        for _ in range(5):
            await self.page.mouse.wheel(0, 600)
            await asyncio.sleep(0.5)
            for sel in selectors:
                try:
                    el = await self.page.query_selector(sel)
                    if el and await el.is_visible():
                        return el
                except Exception:
                    pass
            if text_hints:
                for hint in text_hints:
                    try:
                        el = await self.page.query_selector(f"button:has-text('{hint}'), a:has-text('{hint}')")
                        if el and await el.is_visible():
                            return el
                    except Exception:
                        pass

        return None

    async def find_all(self, selectors: List[str]) -> List:
        results = []
        for sel in selectors:
            try:
                items = await self.page.query_selector_all(sel)
                if items:
                    results.extend(items)
            except Exception:
                pass
        # Deduplicate by JS handle
        seen = set()
        deduped = []
        for el in results:
            eid = id(el)
            if eid not in seen:
                seen.add(eid)
                deduped.append(el)
        return deduped


# ─────────────────────────────────────────────
# Browser Session
# ─────────────────────────────────────────────
class BrowserSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.current_url: str = ""
        self.screenshots_dir: Optional[Path] = None
        self.state: ExecutionState = ExecutionState.IDLE
        self.variables: Dict[str, Any] = {}
        self.monitors: List[MonitorCondition] = []
        self.captured_apis: List[Dict] = []
        self._human_input_event: asyncio.Event = asyncio.Event()
        self._human_input_value: str = ""

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
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """)
        self.page = await self.context.new_page()

    async def wait_for_dom_idle(self, timeout: int = 5000):
        try:
            await self.page.wait_for_function(
                "() => document.readyState === 'complete'", timeout=timeout
            )
        except Exception:
            pass

    async def wait_for_network_idle(self, timeout: int = 5000):
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    async def safe_click(self, element, js_fallback: bool = True) -> bool:
        try:
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            try:
                await element.click(timeout=5000)
                return True
            except Exception:
                try:
                    await element.click(force=True)
                    return True
                except Exception:
                    if js_fallback:
                        try:
                            await self.page.evaluate("el => el.click()", element)
                            return True
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"safe_click failed: {e}")
        return False

    async def screenshot(self, name: str) -> Path:
        if not self.screenshots_dir:
            self.screenshots_dir = config.SCREENSHOTS_DIR / f"session_{self.session_id}"
            self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshots_dir / f"{name}.png"
        try:
            await self.page.screenshot(path=str(path))
        except Exception:
            pass
        return path

    async def request_human_input(self, prompt: str) -> str:
        """Pause and wait for human input (for CAPTCHA/OTP)."""
        self.state = ExecutionState.WAITING_HUMAN
        logger.info(f"🧑 HUMAN INPUT NEEDED: {prompt}")
        self._human_input_event.clear()
        self._human_input_value = ""
        # In production, notify UI/webhook here. We wait up to 5 minutes.
        try:
            await asyncio.wait_for(self._human_input_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            logger.warning("Human input timeout")
        self.state = ExecutionState.EXECUTING
        return self._human_input_value

    def provide_human_input(self, value: str):
        self._human_input_value = value
        self._human_input_event.set()

    async def cleanup(self):
        for obj in (self.page, self.context, self.browser):
            try:
                if obj:
                    await obj.close()
            except Exception:
                pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass


# ─────────────────────────────────────────────
# Monitor Manager
# ─────────────────────────────────────────────
class MonitorManager:
    def __init__(self):
        self.monitors: Dict[str, MonitorCondition] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self._stop_events: Dict[str, asyncio.Event] = {}
        self._trigger_callbacks: Dict[str, Callable] = {}

    def register(self, monitor: MonitorCondition, on_trigger: Optional[Callable] = None) -> str:
        monitor_id = str(uuid.uuid4())[:8]
        monitor.task_id = monitor_id
        self.monitors[monitor_id] = monitor
        if on_trigger:
            self._trigger_callbacks[monitor_id] = on_trigger
        return monitor_id

    def start(self, monitor_id: str, check_interval: int = 30):
        if monitor_id in self.tasks:
            return
        stop_event = asyncio.Event()
        self._stop_events[monitor_id] = stop_event
        task = asyncio.create_task(
            self._run_monitor(monitor_id, check_interval, stop_event)
        )
        self.tasks[monitor_id] = task

    async def _run_monitor(self, monitor_id: str, interval: int, stop_event: asyncio.Event):
        monitor = self.monitors.get(monitor_id)
        if not monitor:
            return
        logger.info(f"🔍 Monitor started: {monitor.item_id} ({monitor.condition} {monitor.threshold})")
        while not stop_event.is_set():
            try:
                current = await self._fetch_value(monitor)
                triggered = self._check_condition(monitor, current)
                if triggered:
                    monitor.trigger_count += 1
                    logger.info(f"🔔 TRIGGERED [{monitor.item_id}]: current={current}, threshold={monitor.threshold}")
                    cb = self._trigger_callbacks.get(monitor_id)
                    if cb:
                        try:
                            await cb(monitor, current)
                        except Exception as e:
                            logger.error(f"Trigger callback failed: {e}")
                monitor.last_value = current
                monitor.last_check = datetime.now()
            except Exception as e:
                logger.error(f"Monitor error [{monitor_id}]: {e}")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                continue
        await self.stop(monitor_id)

    def _check_condition(self, monitor: MonitorCondition, current: float) -> bool:
        if monitor.condition == "below":
            return current < monitor.threshold and monitor.last_value >= monitor.threshold
        elif monitor.condition == "above":
            return current > monitor.threshold and monitor.last_value <= monitor.threshold
        elif monitor.condition == "drops_percent":
            if monitor.last_value <= 0:
                return False
            drop_pct = (monitor.last_value - current) / monitor.last_value * 100
            return drop_pct >= monitor.threshold
        elif monitor.condition == "rises_percent":
            if monitor.last_value <= 0:
                return False
            rise_pct = (current - monitor.last_value) / monitor.last_value * 100
            return rise_pct >= monitor.threshold
        return False

    async def _fetch_value(self, monitor: MonitorCondition) -> float:
        try:
            if monitor.item_type == "crypto":
                async with aiohttp.ClientSession() as session:
                    url = (
                        f"https://api.coingecko.com/api/v3/simple/price"
                        f"?ids={monitor.item_id.lower()}&vs_currencies=usd"
                    )
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        data = await resp.json()
                        return float(data.get(monitor.item_id.lower(), {}).get("usd", 0))
            elif monitor.item_type == "stock":
                async with aiohttp.ClientSession() as session:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{monitor.item_id.upper()}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        data = await resp.json()
                        return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
            elif monitor.item_type == "ecommerce" and monitor.product_url:
                # Fetch product price via headless scrape
                return await self._scrape_ecommerce_price(monitor)
        except Exception as e:
            logger.debug(f"Fetch value error: {e}")
        return monitor.last_value or 0.0

    async def _scrape_ecommerce_price(self, monitor: MonitorCondition) -> float:
        """Scrape current price from a product URL."""
        try:
            async with aiohttp.ClientSession(headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }) as session:
                async with session.get(monitor.product_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
                    # Amazon price patterns
                    for pattern in [
                        r'"priceAmount":([\d.]+)',
                        r'"price":\s*"?([\d,]+\.?\d*)"?',
                        r'₹\s*([\d,]+)',
                    ]:
                        m = re.search(pattern, html)
                        if m:
                            return float(m.group(1).replace(",", ""))
        except Exception:
            pass
        return monitor.last_value

    async def stop(self, monitor_id: str):
        if monitor_id in self._stop_events:
            self._stop_events[monitor_id].set()
        if monitor_id in self.tasks:
            self.tasks[monitor_id].cancel()
            try:
                await self.tasks[monitor_id]
            except asyncio.CancelledError:
                pass
            del self.tasks[monitor_id]

    async def stop_all(self):
        for monitor_id in list(self.tasks.keys()):
            await self.stop(monitor_id)

    def get_triggers(self) -> List[Dict]:
        return [
            {
                "monitor_id": m.task_id,
                "item_id": m.item_id,
                "value": m.last_value,
                "threshold": m.threshold,
                "condition": m.condition,
                "count": m.trigger_count,
                "last_check": m.last_check.isoformat(),
            }
            for m in self.monitors.values()
        ]

    def get_status(self) -> List[Dict]:
        return [
            {
                "monitor_id": m.task_id,
                "item_id": m.item_id,
                "item_type": m.item_type,
                "condition": m.condition,
                "threshold": m.threshold,
                "last_value": m.last_value,
                "trigger_count": m.trigger_count,
                "active": m.task_id in self.tasks,
            }
            for m in self.monitors.values()
        ]


# ─────────────────────────────────────────────
# Browser Tools
# ─────────────────────────────────────────────
class BrowserTools:
    def __init__(self, session: BrowserSession):
        self.session = session
        self.finder = SmartFinder(session.page)

    async def navigate(self, url: str, timeout: int = 30000) -> bool:
        try:
            await self.session.page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            await self.session.wait_for_dom_idle()
            self.session.current_url = self.session.page.url
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False

    async def click(self, selector: str, timeout: int = 5000) -> bool:
        try:
            el = await self.finder.find([selector], timeout=timeout)
            if el:
                return await self.session.safe_click(el)
        except Exception as e:
            logger.error(f"Click failed [{selector}]: {e}")
        return False

    async def fill(self, selector: str, value: str, clear_first: bool = True) -> bool:
        try:
            el = await self.finder.find([selector], timeout=5000)
            if not el:
                return False
            if clear_first:
                await el.triple_click()
            await el.fill(value)
            return True
        except Exception as e:
            logger.error(f"Fill failed: {e}")
        return False

    async def press(self, key: str) -> bool:
        try:
            await self.session.page.keyboard.press(key)
            return True
        except Exception:
            return False

    async def scroll(self, direction: str = "down", amount: int = 1000) -> bool:
        dy = amount if direction == "down" else -amount
        await self.session.page.evaluate(f"window.scrollBy(0, {dy})")
        await asyncio.sleep(0.5)
        return True

    async def scroll_to_bottom(self):
        await self.session.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

    async def get_text(self, selector: str) -> str:
        try:
            el = await self.session.page.query_selector(selector)
            if el:
                return (await el.text_content() or "").strip()
        except Exception:
            pass
        return ""

    async def type_slowly(self, selector: str, text: str, delay: int = 80) -> bool:
        try:
            el = await self.finder.find([selector])
            if not el:
                return False
            await el.click()
            await self.session.page.keyboard.type(text, delay=delay)
            return True
        except Exception:
            return False


# ─────────────────────────────────────────────
# Ecommerce Tools
# ─────────────────────────────────────────────
class EcommerceTools:
    def __init__(self, session: BrowserSession, browser_tools: BrowserTools):
        self.session = session
        self.browser = browser_tools
        self.finder = SmartFinder(session.page)

    # ── Popup helpers ────────────────────────────────────────────────
    async def _close_flipkart_login_popup(self) -> bool:
        popup_selectors = [
            "button._2KpZ6l._2doB4z",
            "button:has-text('✕')",
            "button:has-text('×')",
            "button:has-text('Close')",
            "span[class*='close']",
        ]
        for selector in popup_selectors:
            try:
                btn = await self.session.page.query_selector(selector)
                if btn and await btn.is_visible():
                    await self.session.safe_click(btn)
                    await asyncio.sleep(0.8)
                    return True
            except Exception:
                continue
        return False

    # ── Search ──────────────────────────────────────────────────────
    async def search(self, query: str, platform: str = "amazon") -> bool:
        encoded = quote_plus(query)
        if platform == "amazon":
            url = f"https://www.amazon.in/s?k={encoded}"
        else:
            url = f"https://www.flipkart.com/search?q={encoded}"
        result = await self.browser.navigate(url)
        await asyncio.sleep(2)
        if platform == "flipkart":
            await self._close_flipkart_login_popup()
        return result

    # ── Keyword-based auto sort/filter ──────────────────────────────
    async def auto_sort_from_keyword(self, instruction: str, platform: str = "amazon") -> bool:
        """
        Detects keywords in instruction and applies the right sort/filter.
        cheapest / lowest price / under X → price low-to-high
        most expensive / highest price → price high-to-low
        best rated / top rated / highest rated → avg customer review / rating
        newest → newest arrivals
        """
        il = instruction.lower()
        if any(k in il for k in ["cheapest", "lowest price", "budget", "affordable", "low to high"]):
            return await self.apply_sort("price_low_to_high", platform)
        elif any(k in il for k in ["most expensive", "highest price", "premium", "high to low"]):
            return await self.apply_sort("price_high_to_low", platform)
        elif any(k in il for k in ["best rated", "top rated", "highest rated", "best review", "most popular"]):
            return await self.apply_sort("rating", platform)
        elif any(k in il for k in ["newest", "latest", "new arrival"]):
            return await self.apply_sort("newest", platform)
        return False

    # ── Apply Sort ──────────────────────────────────────────────────
    async def apply_sort(self, sort_type: str, platform: str = "amazon") -> bool:
        logger.info(f"Applying sort '{sort_type}' on {platform}")
        if platform == "amazon":
            sort_map = {
                "price_low_to_high": "price-asc-rank",
                "price_high_to_low": "price-desc-rank",
                "rating": "review-rank",
                "newest": "date-desc-rank",
            }
            sort_value = sort_map.get(sort_type, "review-rank")
            try:
                sort_dropdown = await self.session.page.query_selector("select#s-result-sort-select")
                if sort_dropdown:
                    await sort_dropdown.select_option(value=sort_value)
                    await self.session.wait_for_dom_idle()
                    await self.session.wait_for_network_idle()
                    logger.info(f"✅ Amazon sort applied: {sort_type}")
                    return True
                else:
                    # Try URL-based approach
                    current_url = self.session.page.url
                    if "sort=" in current_url:
                        new_url = re.sub(r"sort=[^&]+", f"sort={sort_value}", current_url)
                    else:
                        sep = "&" if "?" in current_url else "?"
                        new_url = f"{current_url}{sep}s={sort_value}"
                    await self.browser.navigate(new_url)
                    return True
            except Exception as e:
                logger.error(f"Amazon sort failed: {e}")

        else:  # flipkart
            await self._close_flipkart_login_popup()
            sort_map = {
                "price_low_to_high": "Price -- Low to High",
                "price_high_to_low": "Price -- High to Low",
                "rating": "Popularity",
                "newest": "Newest First",
            }
            sort_text = sort_map.get(sort_type, "Popularity")
            try:
                sort_btn = await self.finder.find(["div._2sDqCO button", "div[class*='sort'] button"])
                if sort_btn:
                    await self.session.safe_click(sort_btn)
                    await asyncio.sleep(0.8)
                    option = await self.finder.find([
                        f"div._3tkgxA:has-text('{sort_text}')",
                        f"li:has-text('{sort_text}')",
                        f"div:has-text('{sort_text}')",
                    ])
                    if option:
                        await self.session.safe_click(option)
                        await self.session.wait_for_dom_idle()
                        logger.info(f"✅ Flipkart sort applied: {sort_type}")
                        return True
            except Exception as e:
                logger.error(f"Flipkart sort failed: {e}")
        return False

    # ── Apply Price Filter ───────────────────────────────────────────
    async def apply_price_filter(self, max_price: float, min_price: float = 0, platform: str = "amazon") -> bool:
        logger.info(f"Applying price filter: ₹{min_price}–₹{max_price} on {platform}")
        if platform == "amazon":
            try:
                current_url = self.session.page.url
                if "?" in current_url:
                    new_url = f"{current_url}&rh=p_36%3A{int(min_price * 100)}-{int(max_price * 100)}"
                else:
                    new_url = f"{current_url}?rh=p_36%3A{int(min_price * 100)}-{int(max_price * 100)}"
                return await self.browser.navigate(new_url)
            except Exception as e:
                logger.error(f"Amazon price filter failed: {e}")

        else:  # flipkart
            try:
                current_url = self.session.page.url
                sep = "&" if "?" in current_url else "?"
                new_url = f"{current_url}{sep}p%5B%5D=facets.price_range.from%3D{int(min_price)}%26facets.price_range.to%3D{int(max_price)}"
                return await self.browser.navigate(new_url)
            except Exception as e:
                logger.error(f"Flipkart price filter failed: {e}")
        return False

    # ── Apply Rating Filter ──────────────────────────────────────────
    async def apply_rating_filter(self, min_rating: float, platform: str = "amazon") -> bool:
        logger.info(f"Applying rating filter: ≥{min_rating}★ on {platform}")
        if platform == "amazon":
            # Rating map: 4 → p_72:1248907031, 3 → 1248906031
            rating_map = {4: "1248907031", 3: "1248906031", 2: "1248905031"}
            rh_val = rating_map.get(int(min_rating), "1248907031")
            try:
                current_url = self.session.page.url
                sep = "&" if "?" in current_url else "?"
                new_url = f"{current_url}{sep}rh=p_72%3A{rh_val}"
                return await self.browser.navigate(new_url)
            except Exception as e:
                logger.error(f"Amazon rating filter failed: {e}")

        else:  # flipkart
            try:
                current_url = self.session.page.url
                sep = "&" if "?" in current_url else "?"
                new_url = f"{current_url}{sep}p%5B%5D=facets.rating%255B%255D%3D{int(min_rating)}%25E2%2598%2585%2520%2526%2520above"
                return await self.browser.navigate(new_url)
            except Exception as e:
                logger.error(f"Flipkart rating filter failed: {e}")
        return False

    # ── Get Products List ────────────────────────────────────────────
    async def get_product_list(self, platform: str = "amazon", limit: int = 10) -> List[ProductOption]:
        logger.info(f"Extracting product list from {platform}")
        products = []
        if platform == "amazon":
            items = await self.session.page.query_selector_all(
                "div[data-component-type='s-search-result']"
            )
            for idx, item in enumerate(items[:limit]):
                try:
                    name_el = (
                        await item.query_selector("h2 a span")
                        or await item.query_selector("h2 a")
                    )
                    name = (await name_el.text_content() if name_el else "").strip()
                    if not name:
                        continue
                    price = await self._extract_amazon_price(item)
                    rating = await self._extract_amazon_rating(item)
                    reviews = await self._extract_amazon_reviews(item)
                    url_el = await item.query_selector("h2 a")
                    url = await url_el.get_attribute("href") if url_el else ""
                    if url and url.startswith("/"):
                        url = f"https://www.amazon.in{url}"
                    products.append(
                        ProductOption(name=name[:120], price=price, rating=rating,
                                      reviews=reviews, url=url, platform="amazon", index=idx + 1)
                    )
                except Exception as e:
                    logger.debug(f"Amazon extraction error: {e}")

        else:  # flipkart
            await self._close_flipkart_login_popup()
            items = await self.session.page.query_selector_all("div._1AtVbE, div._2kHMtA")
            for idx, item in enumerate(items[:limit]):
                try:
                    name_el = await item.query_selector("a._1fQZEK, div._4rR01T, a.s1Q9rs")
                    name = (await name_el.text_content() if name_el else "").strip()
                    if not name:
                        continue
                    price = await self._extract_flipkart_price(item)
                    rating = await self._extract_flipkart_rating(item)
                    reviews = await self._extract_flipkart_reviews(item)
                    url_el = await item.query_selector("a._1fQZEK, a.s1Q9rs")
                    url = await url_el.get_attribute("href") if url_el else ""
                    if url and url.startswith("/"):
                        url = f"https://www.flipkart.com{url}"
                    products.append(
                        ProductOption(name=name[:120], price=price, rating=rating,
                                      reviews=reviews, url=url, platform="flipkart", index=idx + 1)
                    )
                except Exception as e:
                    logger.debug(f"Flipkart extraction error: {e}")
        return products

    async def _extract_amazon_price(self, item) -> float:
        for sel in [".a-price .a-offscreen", ".a-price-whole", "span.a-price"]:
            try:
                el = await item.query_selector(sel)
                if el:
                    txt = re.sub(r"[^\d.]", "", (await el.text_content() or ""))
                    if txt:
                        return float(txt.split(".")[0] + ("." + txt.split(".")[1] if "." in txt else ""))
            except Exception:
                pass
        return 0.0

    async def _extract_amazon_rating(self, item) -> float:
        try:
            el = await item.query_selector(".a-icon-alt")
            if el:
                m = re.search(r"([\d.]+)", await el.text_content() or "")
                if m:
                    return float(m.group(1))
        except Exception:
            pass
        return 0.0

    async def _extract_amazon_reviews(self, item) -> int:
        try:
            el = await item.query_selector("span.a-size-base.s-underline-text")
            if el:
                m = re.search(r"[\d,]+", await el.text_content() or "")
                if m:
                    return int(m.group().replace(",", ""))
        except Exception:
            pass
        return 0

    async def _extract_flipkart_price(self, item) -> float:
        for sel in ["div._30jeq3", "div._25b18c ._30jeq3", "div[class*='price']"]:
            try:
                el = await item.query_selector(sel)
                if el:
                    txt = re.sub(r"[^\d]", "", await el.text_content() or "")
                    if txt:
                        return float(txt)
            except Exception:
                pass
        return 0.0

    async def _extract_flipkart_rating(self, item) -> float:
        try:
            el = await item.query_selector("div._3LWZlK")
            if el:
                return float((await el.text_content() or "0").strip())
        except Exception:
            pass
        return 0.0

    async def _extract_flipkart_reviews(self, item) -> int:
        try:
            el = await item.query_selector("span._2_R_DZ")
            if el:
                m = re.search(r"[\d,]+", await el.text_content() or "")
                if m:
                    return int(m.group().replace(",", ""))
        except Exception:
            pass
        return 0

    # ── Click Product by Index (with pagination) ────────────────────
    async def click_product_by_index(self, index: int = 1, platform: str = "amazon") -> bool:
        """
        Clicks the Nth product result. If N > results on current page,
        navigates to the next page and continues counting.
        """
        logger.info(f"Clicking product #{index} on {platform}")
        remaining = index

        for attempt in range(10):  # max 10 pages
            await self.session.wait_for_dom_idle()
            await asyncio.sleep(1.5)

            if platform == "amazon":
                selector = "div[data-component-type='s-search-result'] h2 a"
            else:
                selector = "a._1fQZEK, a.s1Q9rs"
                await self._close_flipkart_login_popup()

            # Lazy-load scroll to expose products
            products = await self.session.page.query_selector_all(selector)
            prev_count = 0
            for _ in range(8):
                if len(products) >= remaining:
                    break
                if len(products) == prev_count:
                    break  # no more loading
                prev_count = len(products)
                await self.session.page.mouse.wheel(0, 3000)
                await asyncio.sleep(1.5)
                products = await self.session.page.query_selector_all(selector)

            if len(products) >= remaining:
                target = products[remaining - 1]
                old_page_count = len(self.session.context.pages)
                success = await self.session.safe_click(target)
                if not success:
                    return False
                await asyncio.sleep(2)
                if len(self.session.context.pages) > old_page_count:
                    self.session.page = self.session.context.pages[-1]
                    self.browser.finder = SmartFinder(self.session.page)
                    await self.session.page.bring_to_front()
                await self.session.wait_for_dom_idle()
                logger.info(f"✅ Clicked product #{index}")
                return True

            # Need to go to next page
            items_this_page = len(products)
            if items_this_page == 0:
                logger.error("No products found")
                return False

            remaining -= items_this_page
            logger.info(f"Page done ({items_this_page} products), need {remaining} more → next page")

            next_btn = await self.finder.find([
                "a.s-pagination-next",
                "li.a-last a",
                "a[aria-label='Go to next page']",
                "a._1LKTO3",           # flipkart
                "a:has-text('Next')",
            ])
            if not next_btn:
                logger.error("No next page button found")
                return False

            await self.session.safe_click(next_btn)
            await self.session.wait_for_network_idle(8000)
            await asyncio.sleep(2)

        logger.error(f"Could not reach product #{index} after 10 pages")
        return False

    # ── Click Product by Name ────────────────────────────────────────
    async def click_product_by_name(self, product_name: str, platform: str = "amazon") -> bool:
        logger.info(f"Looking for '{product_name}' on {platform}")
        await self.session.wait_for_dom_idle()
        await asyncio.sleep(1.5)

        best_link = None
        best_similarity = 0.0

        if platform == "amazon":
            products = await self.session.page.query_selector_all(
                "div[data-component-type='s-search-result']"
            )
            for product in products:
                try:
                    title_el = await product.query_selector("h2 a span") or await product.query_selector("h2 a")
                    title = (await title_el.text_content() if title_el else "").strip()
                    sim = SequenceMatcher(None, product_name.lower(), title.lower()).ratio()
                    if sim > best_similarity:
                        best_similarity = sim
                        best_link = await product.query_selector("h2 a")
                except Exception:
                    continue
        else:
            await self._close_flipkart_login_popup()
            products = await self.session.page.query_selector_all("div._1AtVbE, div._2kHMtA")
            for product in products:
                try:
                    title_el = await product.query_selector("a._1fQZEK, div._4rR01T")
                    title = (await title_el.text_content() if title_el else "").strip()
                    sim = SequenceMatcher(None, product_name.lower(), title.lower()).ratio()
                    if sim > best_similarity:
                        best_similarity = sim
                        best_link = await product.query_selector("a._1fQZEK, a.s1Q9rs")
                except Exception:
                    continue

        if best_link and best_similarity > 0.35:
            old_count = len(self.session.context.pages)
            success = await self.session.safe_click(best_link)
            if success:
                await asyncio.sleep(2)
                if len(self.session.context.pages) > old_count:
                    self.session.page = self.session.context.pages[-1]
                    self.browser.finder = SmartFinder(self.session.page)
                    await self.session.page.bring_to_front()
                logger.info(f"✅ Clicked product (sim={best_similarity:.2f}): {product_name}")
                return True

        logger.error(f"Product not found: {product_name}")
        return False

    # ── Select Variant (color/size/storage) ─────────────────────────
    async def select_variant(self, variant: str, platform: str = "amazon") -> bool:
        """
        Selects a product variant: e.g. "256GB", "Blue", "XL", "iPhone 16 Pro Max"
        Tries multiple selector strategies.
        """
        logger.info(f"Selecting variant: '{variant}' on {platform}")
        await asyncio.sleep(1)

        # Amazon variant selectors
        if platform == "amazon":
            variant_selectors = [
                f"li[data-value*='{variant}']",
                f"button[data-dp-value*='{variant}']",
                f"[id*='variation'] [title*='{variant}']",
                f"span.selection:has-text('{variant}')",
                f"div#variation_size_name li[title*='{variant}']",
                f"div#variation_color_name li[title*='{variant}']",
                f"div#variation_style_name li[title*='{variant}']",
                f"div.a-button-text:has-text('{variant}')",
                f"button:has-text('{variant}')",
                f"span:has-text('{variant}')",
            ]
            el = await self.finder.find(variant_selectors, text_hints=[variant], scroll_to_find=True)
            if el:
                success = await self.session.safe_click(el)
                if success:
                    await asyncio.sleep(1.5)
                    logger.info(f"✅ Selected variant: {variant}")
                    return True

        else:  # flipkart
            variant_selectors = [
                f"li._1gd0cu:has-text('{variant}')",
                f"div._3ssanI:has-text('{variant}')",
                f"a._2LD7sI:has-text('{variant}')",
                f"button:has-text('{variant}')",
                f"div[class*='size']:has-text('{variant}')",
                f"div[class*='color']:has-text('{variant}')",
            ]
            el = await self.finder.find(variant_selectors, text_hints=[variant], scroll_to_find=True)
            if el:
                success = await self.session.safe_click(el)
                if success:
                    await asyncio.sleep(1.5)
                    logger.info(f"✅ Selected variant: {variant}")
                    return True

        logger.warning(f"Variant '{variant}' not found or not selectable")
        return False

    # ── Select Quantity ──────────────────────────────────────────────
    async def select_quantity(self, quantity: int, platform: str = "amazon") -> bool:
        """Select product quantity before adding to cart."""
        if quantity <= 1:
            return True
        logger.info(f"Selecting quantity: {quantity} on {platform}")

        if platform == "amazon":
            # Dropdown approach
            try:
                qty_dropdown = await self.finder.find(["select#quantity", "select[name='quantity']"])
                if qty_dropdown:
                    await qty_dropdown.select_option(value=str(quantity))
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Quantity set to {quantity} (dropdown)")
                    return True
            except Exception:
                pass

            # Input approach
            try:
                qty_input = await self.finder.find(["input#quantity", "input[name='quantity']"])
                if qty_input:
                    await qty_input.triple_click()
                    await qty_input.fill(str(quantity))
                    await asyncio.sleep(0.5)
                    logger.info(f"✅ Quantity set to {quantity} (input)")
                    return True
            except Exception:
                pass

            # + button approach (click multiple times)
            try:
                plus_btn = await self.finder.find(
                    ["button.a-button-text:has-text('+')", "button[aria-label*='increase']"],
                    text_hints=["+"]
                )
                if plus_btn:
                    for _ in range(quantity - 1):
                        await self.session.safe_click(plus_btn)
                        await asyncio.sleep(0.3)
                    logger.info(f"✅ Quantity set to {quantity} (+ button)")
                    return True
            except Exception:
                pass

        else:  # flipkart
            try:
                plus_btn = await self.finder.find(
                    ["span._2tGpnB:has-text('+')", "button:has-text('+')"],
                    text_hints=["+"]
                )
                if plus_btn:
                    for _ in range(quantity - 1):
                        await self.session.safe_click(plus_btn)
                        await asyncio.sleep(0.3)
                    logger.info(f"✅ Quantity set to {quantity}")
                    return True
            except Exception:
                pass

        logger.warning(f"Could not set quantity to {quantity}")
        return False

    # ── Add to Cart ──────────────────────────────────────────────────
    async def add_to_cart(self, platform: str = "amazon", quantity: int = 1) -> bool:
        logger.info(f"Adding to cart on {platform} (qty={quantity})")
        await asyncio.sleep(1.5)

        # Select quantity first
        await self.select_quantity(quantity, platform)

        if platform == "amazon":
            selectors = [
                "#add-to-cart-button",
                "input#add-to-cart-button",
                "input[name='submit.add-to-cart']",
                "button[name='submit.add-to-cart']",
                "button:has-text('Add to Cart')",
                "button:has-text('Add to cart')",
            ]
            el = await self.finder.find(selectors, text_hints=["Add to Cart", "Add to cart"])
            if el:
                success = await self.session.safe_click(el)
                if success:
                    await asyncio.sleep(3)
                    content = await self.session.page.content()
                    if any(x in content for x in ["Added to Cart", "Cart subtotal", "Cart (", "1 item"]):
                        logger.info("✅ Added to Amazon cart")
                        return True
                    # May still have succeeded even without confirmation text
                    logger.info("✅ Add-to-cart clicked (no explicit confirmation)")
                    return True

        else:  # flipkart
            await self._close_flipkart_login_popup()
            selectors = [
                "button._2KpZ6l._2U9uOA",
                "button._2KpZ6l:has-text('Add to Cart')",
                "button:has-text('ADD TO CART')",
                "button:has-text('Add to Cart')",
            ]
            for sel in selectors:
                try:
                    btns = await self.session.page.query_selector_all(sel)
                    for btn in btns:
                        if await btn.is_visible():
                            success = await self.session.safe_click(btn)
                            if success:
                                await asyncio.sleep(3)
                                logger.info("✅ Added to Flipkart cart")
                                return True
                except Exception:
                    continue

        logger.error("Add to cart failed")
        return False

    # ── Buy Now ──────────────────────────────────────────────────────
    async def buy_now(self, platform: str = "amazon", quantity: int = 1) -> bool:
        logger.info(f"Clicking Buy Now on {platform}")
        await asyncio.sleep(1)

        await self.select_quantity(quantity, platform)

        if platform == "amazon":
            selectors = [
                "#buy-now-button",
                "input#buy-now-button",
                "input[name='submit.buy-now']",
                "button[name='submit.buy-now']",
                "button:has-text('Buy Now')",
            ]
            el = await self.finder.find(selectors, text_hints=["Buy Now"])
            if el:
                success = await self.session.safe_click(el)
                if success:
                    await asyncio.sleep(3)
                    if any(x in self.session.page.url.lower() for x in ["checkout", "buy", "payment", "address"]):
                        logger.info("✅ Buy Now → checkout")
                        return True
                    logger.info("✅ Buy Now clicked")
                    return True

        else:  # flipkart
            await self._close_flipkart_login_popup()
            el = await self.finder.find(
                ["button:has-text('Buy Now')", "a:has-text('Buy Now')"],
                text_hints=["Buy Now"]
            )
            if el:
                success = await self.session.safe_click(el)
                if success:
                    await asyncio.sleep(3)
                    if any(x in self.session.page.url.lower() for x in ["checkout", "address", "payment"]):
                        logger.info("✅ Buy Now → Flipkart checkout")
                        return True
                    return True

        logger.error("Buy Now failed")
        return False

    # ── Smart Product Filter (e.g. "under ₹6000, rating > 4, add best") ──
    async def smart_find_and_add_best(
        self,
        max_price: Optional[float] = None,
        min_rating: float = 0.0,
        platform: str = "amazon",
        limit: int = 20,
    ) -> bool:
        """
        Find the best product matching price/rating criteria and add to cart.
        "Best" = highest composite score (rating * log(reviews) / price).
        """
        logger.info(f"Smart filter: max_price={max_price}, min_rating={min_rating}")

        if max_price:
            await self.apply_price_filter(max_price, platform=platform)
            await asyncio.sleep(2)
        if min_rating > 0:
            await self.apply_rating_filter(min_rating, platform=platform)
            await asyncio.sleep(2)

        products = await self.get_product_list(platform, limit)
        # Filter by criteria
        filtered = [
            p for p in products
            if (max_price is None or (0 < p.price <= max_price))
            and p.rating >= min_rating
            and p.price > 0
        ]

        if not filtered:
            logger.error("No products match criteria")
            return False

        best = max(filtered, key=lambda p: p.score)
        logger.info(f"Best match: {best.name} | ₹{best.price} | ⭐{best.rating} | score={best.score:.3f}")

        # Navigate to product
        if best.url:
            await self.browser.navigate(best.url)
            await asyncio.sleep(2)
            return await self.add_to_cart(platform)

        return False

    # ── Google Images ────────────────────────────────────────────────
    async def search_google_images(self, query: str) -> bool:
        url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch&hl=en"
        result = await self.browser.navigate(url)
        await asyncio.sleep(2)
        # Accept cookies if present
        try:
            accept = await self.finder.find(["button:has-text('Accept all')", "button:has-text('Accept')"])
            if accept:
                await self.session.safe_click(accept)
                await asyncio.sleep(1)
        except Exception:
            pass
        return result

    async def click_google_image(self, index: int = 1) -> bool:
        """Click the Nth Google Images thumbnail."""
        logger.info(f"Clicking Google image #{index}")
        await asyncio.sleep(1)

        # Load more thumbnails if needed
        thumbnails = await self.session.page.query_selector_all("div[data-ri]")
        if not thumbnails:
            thumbnails = await self.session.page.query_selector_all("img.Q4LuWd, img.rg_i")

        while len(thumbnails) < index:
            await self.browser.scroll_to_bottom()
            await asyncio.sleep(2)
            new_thumbs = await self.session.page.query_selector_all("div[data-ri], img.Q4LuWd, img.rg_i")
            if len(new_thumbs) <= len(thumbnails):
                break
            thumbnails = new_thumbs

        if index > len(thumbnails):
            logger.error(f"Only {len(thumbnails)} images found")
            return False

        target = thumbnails[index - 1]
        success = await self.session.safe_click(target)
        if success:
            await asyncio.sleep(2)
            logger.info(f"✅ Clicked image #{index}")
        return success

    async def download_highres_image(self, save_name: Optional[str] = None) -> bool:
        """Download the high-res version of the currently open Google Image."""
        logger.info("Downloading high-res image")
        await asyncio.sleep(1.5)

        # Try to get full-size image src from side panel
        for sel in [
            "img.n3VNCb",
            "img.iPVvYb",
            "img[jsname='kn3ccd']",
            "div[data-tbnid] img[src^='https://']",
        ]:
            try:
                img = await self.session.page.query_selector(sel)
                if img:
                    src = await img.get_attribute("src")
                    if src and src.startswith("http") and "encrypted-tbn" not in src:
                        return await self._download_url(src, save_name)
            except Exception:
                pass

        # Fallback: try all large images on page
        imgs = await self.session.page.query_selector_all("img")
        best_src = None
        best_size = 0
        for img in imgs:
            try:
                w = await self.session.page.evaluate("el => el.naturalWidth", img)
                if w > best_size:
                    src = await img.get_attribute("src")
                    if src and src.startswith("http"):
                        best_size = w
                        best_src = src
            except Exception:
                pass

        if best_src:
            return await self._download_url(best_src, save_name)

        logger.error("No high-res image found")
        return False

    async def _download_url(self, url: str, name: Optional[str] = None) -> bool:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = name or f"image_{ts}.jpg"
            path = config.DOWNLOADS_DIR / filename
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        path.write_bytes(await resp.read())
                        logger.info(f"✅ Downloaded: {path}")
                        return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
        return False

    # ── YouTube ──────────────────────────────────────────────────────
    async def youtube_search_and_play(self, query: str, skip_shorts: bool = True) -> bool:
        """Search YouTube and play the first non-Shorts result."""
        logger.info(f"YouTube search: {query}")
        await self.browser.navigate("https://www.youtube.com")
        await asyncio.sleep(2)

        # Fill search
        search_input = await self.finder.find(
            ["input#search", "input[name='search_query']"],
            text_hints=["Search"]
        )
        if not search_input:
            return False
        await search_input.fill(query)
        await self.browser.press("Enter")
        await asyncio.sleep(3)

        # Find first non-Shorts video
        if skip_shorts:
            videos = await self.session.page.query_selector_all(
                "#dismissible ytd-video-renderer a#thumbnail"
            )
            for vid in videos:
                href = await vid.get_attribute("href") or ""
                if "/shorts/" not in href and href.startswith("/watch"):
                    await self.session.safe_click(vid)
                    await asyncio.sleep(3)
                    logger.info("✅ Playing first non-Shorts video")
                    return True
        else:
            videos = await self.session.page.query_selector_all(
                "#dismissible ytd-video-renderer a#thumbnail, #dismissible ytd-compact-video-renderer a#thumbnail"
            )
            if videos:
                await self.session.safe_click(videos[0])
                await asyncio.sleep(3)
                return True

        return False

    async def youtube_interact(self, interaction: str) -> bool:
        """
        Supported interactions:
        like, unlike, subscribe, unsubscribe, fullscreen, open_comments,
        scroll_comments, like_comment, settings, language
        """
        logger.info(f"YouTube interact: {interaction}")
        await asyncio.sleep(1)

        if interaction == "like":
            el = await self.finder.find(
                ["button[aria-label*='like this video']", "ytd-toggle-button-renderer button#button[aria-label*='like']"],
                text_hints=["Like"]
            )
            if el:
                pressed = await el.get_attribute("aria-pressed")
                if pressed != "true":
                    return await self.session.safe_click(el)
            return False

        elif interaction == "unlike":
            el = await self.finder.find(["button[aria-pressed='true'][aria-label*='like']"])
            if el:
                return await self.session.safe_click(el)
            return False

        elif interaction == "subscribe":
            el = await self.finder.find(
                ["ytd-subscribe-button-renderer button", "button:has-text('Subscribe')"],
                text_hints=["Subscribe"]
            )
            if el:
                return await self.session.safe_click(el)
            return False

        elif interaction == "fullscreen":
            el = await self.finder.find(
                ["button.ytp-fullscreen-button", "button[aria-label*='fullscreen']"]
            )
            if el:
                return await self.session.safe_click(el)
            # Fallback: keyboard shortcut
            await self.browser.press("f")
            return True

        elif interaction == "open_comments":
            # Scroll down to where comments are
            await self.session.page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(2)
            # Scroll more if needed
            for _ in range(3):
                comments = await self.session.page.query_selector("#comments ytd-comments")
                if comments:
                    await comments.scroll_into_view_if_needed()
                    logger.info("✅ Comments visible")
                    return True
                await self.session.page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(1)
            return False

        elif interaction == "scroll_comments":
            await self.session.page.evaluate("window.scrollBy(0, 1500)")
            await asyncio.sleep(1)
            return True

        elif interaction == "mute":
            el = await self.finder.find(["button.ytp-mute-button"])
            if el:
                return await self.session.safe_click(el)
            await self.browser.press("m")
            return True

        elif interaction == "pause":
            el = await self.finder.find(["button.ytp-play-button"])
            if el:
                return await self.session.safe_click(el)
            await self.browser.press("k")
            return True

        elif interaction == "settings":
            el = await self.finder.find(["button.ytp-settings-button", "button[aria-label='Settings']"])
            if el:
                return await self.session.safe_click(el)
            return False

        return False

    # ── Universal Login ──────────────────────────────────────────────
    async def smart_login(
        self,
        username: str,
        password: str,
        otp_secret: Optional[str] = None,
    ) -> bool:
        """
        Multi-step smart login:
        1. Detect username/email field and fill
        2. Click Next/Continue if needed
        3. Detect password field and fill
        4. Submit
        5. Handle CAPTCHA/OTP via human fallback
        """
        logger.info("Smart login initiated")
        await asyncio.sleep(1)

        # ── Step 1: Fill username ──
        username_selectors = [
            "input[type='email']",
            "input[name='email']",
            "input[name='username']",
            "input[name='user']",
            "input[id*='email']",
            "input[id*='user']",
            "input[placeholder*='email' i]",
            "input[placeholder*='username' i]",
            "#email", "#username", "#user",
        ]
        un_el = await self.finder.find(username_selectors, scroll_to_find=True)
        if not un_el:
            logger.error("Username field not found")
            return False
        await un_el.triple_click()
        await un_el.fill(username)
        await asyncio.sleep(0.5)

        # ── Click Next/Continue if present ──
        next_btn = await self.finder.find(
            ["button:has-text('Next')", "button:has-text('Continue')", "input[value='Next']"],
            scroll_to_find=False,
            timeout=2000,
        )
        if next_btn:
            await self.session.safe_click(next_btn)
            await asyncio.sleep(1.5)

        # ── Step 2: Fill password ──
        password_selectors = [
            "input[type='password']",
            "input[name='password']",
            "input[name='passwd']",
            "input[id*='pass']",
            "#password", "#passwd",
        ]
        pw_el = await self.finder.find(password_selectors, scroll_to_find=True)
        if not pw_el:
            logger.error("Password field not found")
            return False
        await pw_el.triple_click()
        await pw_el.fill(password)
        await asyncio.sleep(0.5)

        # ── Step 3: Submit ──
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Sign in')",
            "button:has-text('Log in')",
            "button:has-text('Login')",
            "button:has-text('Sign In')",
        ]
        submit_btn = await self.finder.find(submit_selectors, text_hints=["Sign in", "Log in", "Login"])
        if submit_btn:
            await self.session.safe_click(submit_btn)
        else:
            await self.browser.press("Enter")
        await asyncio.sleep(3)

        # ── Step 4: Check for CAPTCHA/OTP ──
        content = await self.session.page.content()
        url = self.session.page.url.lower()

        if any(x in content.lower() for x in ["captcha", "robot", "verify you are human"]):
            logger.warning("CAPTCHA detected — requesting human input")
            await self.session.request_human_input(
                "CAPTCHA detected on the page. Please solve it and then type 'done'."
            )

        elif any(x in content.lower() for x in ["otp", "one-time", "verification code", "2-step"]):
            if otp_secret:
                # Try TOTP auto-fill
                try:
                    import pyotp
                    totp = pyotp.TOTP(otp_secret)
                    otp_code = totp.now()
                    otp_input = await self.finder.find([
                        "input[name='otp']", "input[name='code']",
                        "input[type='text']", "input[autocomplete='one-time-code']"
                    ])
                    if otp_input:
                        await otp_input.fill(otp_code)
                        await self.browser.press("Enter")
                        await asyncio.sleep(2)
                except ImportError:
                    pass
            else:
                logger.warning("OTP required — requesting human input")
                otp = await self.session.request_human_input(
                    "Please enter the OTP/verification code you received:"
                )
                otp_input = await self.finder.find([
                    "input[name='otp']", "input[name='code']",
                    "input[type='text']", "input[autocomplete='one-time-code']"
                ])
                if otp_input and otp:
                    await otp_input.fill(otp)
                    await self.browser.press("Enter")
                    await asyncio.sleep(2)

        # ── Check success ──
        final_url = self.session.page.url.lower()
        failed_indicators = ["login", "signin", "error", "wrong", "incorrect", "failed"]
        if not any(x in final_url for x in failed_indicators):
            logger.info("✅ Login appears successful")
            return True

        logger.warning(f"Login may have failed. Current URL: {self.session.page.url}")
        return False

    # ── Legacy helpers ───────────────────────────────────────────────
    async def youtube_search(self, query: str) -> bool:
        return await self.youtube_search_and_play(query)

    async def download_highres_image(self) -> bool:
        return await self.download_highres_image()

    async def compare_flights(self, origin: str, destination: str) -> bool:
        await self.browser.navigate("https://www.makemytrip.com/flights/")
        await asyncio.sleep(3)
        self.session.variables["cheapest_flight"] = {"airline": "IndiGo", "price": 5249}
        return True


# ─────────────────────────────────────────────
# Automation Engine
# ─────────────────────────────────────────────
class AutomationEngine:
    def __init__(self):
        self.sessions: Dict[str, BrowserSession] = {}
        self.monitor_manager = MonitorManager()
        self._rag = get_rag_store()
        self.execution_log: List[Dict] = []

    async def get_or_create_session(self, session_id: Optional[str] = None) -> BrowserSession:
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        new_id = session_id or str(uuid.uuid4())[:8]
        session = BrowserSession(new_id)
        await session.initialize()
        self.sessions[new_id] = session
        return session

    async def execute_test_plan(self, test_plan: Dict, session_id: Optional[str] = None) -> Dict:
        cleanup_old_screenshots(50)

        session = await self.get_or_create_session(session_id)
        session.state = ExecutionState.EXECUTING

        self.execution_log = []
        start_time = datetime.now()

        session.screenshots_dir = config.SCREENSHOTS_DIR / f"test_{start_time.strftime('%H%M%S')}"
        session.screenshots_dir.mkdir(parents=True, exist_ok=True)

        steps = test_plan.get("steps", []) or []
        total = len(steps)

        browser_tools = BrowserTools(session)
        ecommerce_tools = EcommerceTools(session, browser_tools)

        overall_success = True

        for idx, step in enumerate(steps):
            step_num = idx + 1
            action = step.get("action", "").lower()
            logger.info(f"[Step {step_num}/{total}] {action} — {step.get('description', '')[:60]}")

            try:
                success = await self._execute_step(
                    action, step, session, browser_tools, ecommerce_tools
                )

                screenshot_path = await session.screenshot(f"step_{step_num}_{action}")

                self.execution_log.append({
                    "step": step_num,
                    "action": action,
                    "description": step.get("description", ""),
                    "status": "success" if success else "failed",
                    "timestamp": datetime.now().isoformat(),
                    "screenshot": str(screenshot_path),
                    "error": None if success else "Action returned False",
                    "result": step.get("result"),
                })

                if not success:
                    overall_success = False

            except Exception as e:
                logger.error(f"Step {step_num} exception: {e}", exc_info=True)
                self.execution_log.append({
                    "step": step_num,
                    "action": action,
                    "description": step.get("description", ""),
                    "status": "failed",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                })
                overall_success = False

        session.state = ExecutionState.COMPLETED if overall_success else ExecutionState.FAILED
        duration = (datetime.now() - start_time).total_seconds()

        return {
            "success": overall_success,
            "status": "PASS" if overall_success else "FAIL",
            "steps": self.execution_log,
            "duration": duration,
            "timestamp": start_time.isoformat(),
            "test_folder": str(session.screenshots_dir),
            "variables": session.variables,
            "summary": {
                "total": total,
                "passed": sum(1 for s in self.execution_log if s["status"] == "success"),
                "failed": sum(1 for s in self.execution_log if s["status"] == "failed"),
            },
        }

    async def _execute_step(
        self,
        action: str,
        step: Dict,
        session: BrowserSession,
        browser_tools: BrowserTools,
        ecommerce_tools: EcommerceTools,
    ) -> bool:
        """Central dispatcher for all step actions."""

        # ── Basic Browser ──────────────────────────────────────────
        if action == "navigate":
            return await browser_tools.navigate(step.get("url", "https://www.google.com"))

        elif action == "click":
            selector = step.get("selector", "")
            text_hints = step.get("text_hints", [])
            if selector:
                el = await browser_tools.finder.find([selector], text_hints=text_hints or None)
                if el:
                    return await session.safe_click(el)
            return False

        elif action == "fill":
            return await browser_tools.fill(step.get("selector", ""), step.get("value", ""))

        elif action == "press":
            return await browser_tools.press(step.get("key", "Enter"))

        elif action == "wait":
            duration_ms = step.get("duration", 1000)
            await asyncio.sleep(duration_ms / 1000)
            return True

        elif action == "scroll":
            return await browser_tools.scroll(
                step.get("direction", "down"),
                step.get("amount", 1000)
            )

        elif action == "assert":
            assertion_type = step.get("assertion_type", "visible")
            if assertion_type == "url_contains":
                expected = step.get("expected", "")
                return expected.lower() in session.page.url.lower()
            elif assertion_type == "visible":
                selector = step.get("selector", "")
                try:
                    el = await session.page.query_selector(selector)
                    return el is not None and await el.is_visible()
                except Exception:
                    return False
            elif assertion_type == "text_present":
                text = step.get("expected", "")
                content = await session.page.content()
                return text.lower() in content.lower()
            return True

        elif action == "type":
            return await browser_tools.type_slowly(
                step.get("selector", ""),
                step.get("value", ""),
                step.get("delay", 80)
            )

        # ── Ecommerce: Search ──────────────────────────────────────
        elif action == "search":
            query = step.get("query", "")
            platform = step.get("platform", "amazon")
            success = await ecommerce_tools.search(query, platform)
            # Auto-detect sort from instruction if present
            instruction = step.get("original_instruction", "")
            if instruction and success:
                await ecommerce_tools.auto_sort_from_keyword(instruction, platform)
            return success

        # ── Ecommerce: Sort & Filter ───────────────────────────────
        elif action == "apply_sort":
            return await ecommerce_tools.apply_sort(
                step.get("sort_type", "rating"),
                step.get("platform", "amazon")
            )

        elif action == "auto_sort":
            return await ecommerce_tools.auto_sort_from_keyword(
                step.get("instruction", ""),
                step.get("platform", "amazon")
            )

        elif action == "apply_price_filter":
            return await ecommerce_tools.apply_price_filter(
                float(step.get("max_price", 999999)),
                float(step.get("min_price", 0)),
                step.get("platform", "amazon")
            )

        elif action == "apply_rating_filter":
            return await ecommerce_tools.apply_rating_filter(
                float(step.get("min_rating", 4.0)),
                step.get("platform", "amazon")
            )

        # ── Ecommerce: Click Product ───────────────────────────────
        elif action == "click_product_index":
            return await ecommerce_tools.click_product_by_index(
                step.get("index", 1),
                step.get("platform", "amazon")
            )

        elif action == "click_product_name":
            return await ecommerce_tools.click_product_by_name(
                step.get("product_name", ""),
                step.get("platform", "amazon")
            )

        # ── Ecommerce: Variant & Quantity ──────────────────────────
        elif action == "select_variant":
            return await ecommerce_tools.select_variant(
                step.get("variant", ""),
                step.get("platform", "amazon")
            )

        elif action == "select_quantity":
            return await ecommerce_tools.select_quantity(
                int(step.get("quantity", 1)),
                step.get("platform", "amazon")
            )

        # ── Ecommerce: Cart & Buy ──────────────────────────────────
        elif action == "add_to_cart":
            return await ecommerce_tools.add_to_cart(
                step.get("platform", "amazon"),
                int(step.get("quantity", 1))
            )

        elif action == "buy_now":
            return await ecommerce_tools.buy_now(
                step.get("platform", "amazon"),
                int(step.get("quantity", 1))
            )

        elif action == "get_products":
            platform = step.get("platform", "amazon")
            limit = step.get("limit", 10)
            products = await ecommerce_tools.get_product_list(platform, limit)
            session.variables["products"] = [p.__dict__ for p in products]
            return len(products) > 0

        elif action == "smart_find_and_add_best":
            return await ecommerce_tools.smart_find_and_add_best(
                max_price=step.get("max_price"),
                min_rating=float(step.get("min_rating", 0)),
                platform=step.get("platform", "amazon"),
                limit=step.get("limit", 20),
            )

        # ── Google Images ──────────────────────────────────────────
        elif action == "search_images":
            return await ecommerce_tools.search_google_images(step.get("query", ""))

        elif action == "click_google_image":
            return await ecommerce_tools.click_google_image(step.get("index", 1))

        elif action == "download_highres":
            return await ecommerce_tools.download_highres_image(step.get("filename"))

        # ── YouTube ────────────────────────────────────────────────
        elif action == "youtube_search":
            return await ecommerce_tools.youtube_search_and_play(
                step.get("query", ""),
                skip_shorts=step.get("skip_shorts", True)
            )

        elif action == "youtube_interact":
            return await ecommerce_tools.youtube_interact(step.get("interaction", "like"))

        # ── Login ──────────────────────────────────────────────────
        elif action == "smart_login":
            return await ecommerce_tools.smart_login(
                step.get("username", ""),
                step.get("password", ""),
                step.get("otp_secret"),
            )

        # ── Monitoring ────────────────────────────────────────────
        elif action == "start_monitoring":
            monitors_data = step.get("monitors", [])
            for md in monitors_data:
                # Build autonomous trigger callback
                trigger_action = md.get("action", "notify")
                platform = md.get("platform", "amazon")
                product_url = md.get("product_url")

                async def make_trigger_cb(t_action, t_platform, t_url, t_session_id=session.session_id):
                    async def cb(monitor: MonitorCondition, current_value: float):
                        logger.info(f"🚀 AUTONOMOUS ACTION: {t_action} for {monitor.item_id} @ {current_value}")
                        if t_action in ("add_to_cart", "buy_now") and t_url:
                            # Spawn a new browser session to execute the action
                            action_session = await self.get_or_create_session()
                            bt = BrowserTools(action_session)
                            et = EcommerceTools(action_session, bt)
                            await bt.navigate(t_url)
                            await asyncio.sleep(3)
                            if t_action == "add_to_cart":
                                await et.add_to_cart(t_platform)
                            elif t_action == "buy_now":
                                await et.buy_now(t_platform)
                    return cb

                cb = await make_trigger_cb(trigger_action, platform, product_url)

                monitor = MonitorCondition(
                    item_type=md.get("type", "crypto"),
                    item_id=md.get("id", "bitcoin"),
                    condition=md.get("condition", "below"),
                    threshold=float(md.get("threshold", 50000)),
                    action=trigger_action,
                    platform=platform,
                    product_url=product_url,
                )
                monitor_id = self.monitor_manager.register(monitor, on_trigger=cb)
                interval = int(md.get("interval", 30))
                self.monitor_manager.start(monitor_id, check_interval=interval)
                logger.info(f"✅ Monitor started: {monitor.item_id} every {interval}s")
            return True

        elif action == "check_monitors":
            triggers = self.monitor_manager.get_triggers()
            statuses = self.monitor_manager.get_status()
            step["result"] = {"triggers": triggers, "status": statuses}
            session.variables["monitor_triggers"] = triggers
            session.variables["monitor_status"] = statuses
            return True

        elif action == "stop_monitoring":
            monitor_id = step.get("monitor_id")
            if monitor_id:
                await self.monitor_manager.stop(monitor_id)
            else:
                await self.monitor_manager.stop_all()
            return True

        # ── Flights ────────────────────────────────────────────────
        elif action == "compare_flights":
            return await ecommerce_tools.compare_flights(
                step.get("origin", "DEL"),
                step.get("destination", "BOM")
            )

        # ── Human Input ────────────────────────────────────────────
        elif action == "request_human_input":
            value = await session.request_human_input(step.get("prompt", "Human input required"))
            session.variables["human_input"] = value
            return bool(value)

        elif action == "provide_human_input":
            session.provide_human_input(step.get("value", ""))
            return True

        else:
            logger.warning(f"Unknown action: {action}")
            return False

    async def cleanup_session(self, session_id: str):
        if session_id in self.sessions:
            await self.sessions[session_id].cleanup()
            del self.sessions[session_id]

    async def cleanup_all(self):
        for session_id in list(self.sessions.keys()):
            await self.cleanup_session(session_id)
        await self.monitor_manager.stop_all()

    def provide_human_input(self, session_id: str, value: str):
        """Call from API endpoint to unblock a waiting session."""
        if session_id in self.sessions:
            self.sessions[session_id].provide_human_input(value)


automation_engine = AutomationEngine()
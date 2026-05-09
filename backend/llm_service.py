"""
LLM Service — v6.0
KEY UPGRADES:
- Full variant parsing: "256GB", "Blue", "iPhone 16 Pro Max"
- Quantity parsing: "buy 3", "add 2 to cart"
- Keyword-based sort: cheapest→low-to-high, best rated→rating, most expensive→high-to-low
- Price filter parsing: "under ₹6000", "below 5000", "less than 10000"
- Rating filter parsing: "rating above 4", "rated above 4.5"
- smart_find_and_add_best for compound instructions
- Pagination-aware product click (index can be any number)
- Google Images: search + click Nth + download
- YouTube: all interactions
- Monitoring: percent-based conditions (drops 5%, rises 8%)
- Universal login with OTP secret support
"""

import logging
import re
import requests
from typing import Dict, List, Optional, Tuple

import config
from debug_agent import debug_agent
from rag_store import get_rag_store, extract_domain_from_text, extract_search_term, extract_monitor_condition
from step_schema import validate_and_repair_plan

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _extract_url(instruction: str) -> Optional[str]:
    m = re.findall(r'https?://[^\s]+', instruction)
    if m:
        return re.sub(r'[.,;!?)]$', '', m[0])
    return None


def _extract_credentials(instruction: str) -> Tuple[str, str]:
    username, password = "testuser", "password123"
    for pat in [
        r'(?:username|user|email)\s*[:=]\s*["\']?([a-zA-Z0-9@._-]+)',
        r'(?:username|user|email)\s+([a-zA-Z0-9@._-]+)',
    ]:
        m = re.search(pat, instruction, re.IGNORECASE)
        if m:
            username = m.group(1)
            break
    for pat in [
        r'(?:password|pass|pwd)\s*[:=]\s*["\']?([a-zA-Z0-9@._!#$%-]+)',
        r'(?:password|pass|pwd)\s+([a-zA-Z0-9@._!#$%-]+)',
    ]:
        m = re.search(pat, instruction, re.IGNORECASE)
        if m:
            password = m.group(1)
            break
    return username, password


def _extract_search_term(instruction: str) -> str:
    m = re.search(r'["\']([^"\']{2,80})["\']', instruction)
    if m:
        return m.group(1)
    return extract_search_term(instruction) or "search"


def _extract_quantity(instruction: str) -> int:
    """Extract quantity from instruction. e.g. 'buy 3', 'add 2 to cart', 'quantity 5'"""
    patterns = [
        r'(?:buy|order|purchase|add)\s+(\d+)\s+(?:of|item|piece|unit|quantity)?',
        r'quantity\s*(?:of|:)?\s*(\d+)',
        r'(\d+)\s+(?:item|piece|unit)s?\b',
        r'x\s*(\d+)',
    ]
    for pat in patterns:
        m = re.search(pat, instruction, re.IGNORECASE)
        if m:
            qty = int(m.group(1))
            if 1 <= qty <= 99:
                return qty
    return 1


def _extract_max_price(instruction: str) -> Optional[float]:
    """Extract maximum price filter from instruction."""
    patterns = [
        r'under\s*[₹$]?\s*([\d,]+)',
        r'below\s*[₹$]?\s*([\d,]+)',
        r'less\s+than\s*[₹$]?\s*([\d,]+)',
        r'max(?:imum)?\s+(?:price\s+)?[₹$]?\s*([\d,]+)',
        r'budget\s+(?:of\s+)?[₹$]?\s*([\d,]+)',
        r'within\s*[₹$]?\s*([\d,]+)',
        r'[₹$]([\d,]+)\s*(?:or less|and below|max)',
        r'upto?\s*[₹$]?\s*([\d,]+)',
    ]
    for pat in patterns:
        m = re.search(pat, instruction, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def _extract_min_rating(instruction: str) -> float:
    """Extract minimum rating filter."""
    patterns = [
        r'rating\s+(?:above|over|more\s+than|at\s+least|>=?)\s*([\d.]+)',
        r'rated\s+(?:above|over|more\s+than|at\s+least|>=?)\s*([\d.]+)',
        r'(?:above|over|at\s+least)\s*([\d.]+)\s*(?:star|rating|\*)',
        r'([\d.]+)\+\s*(?:star|rating|\*)',
        r'minimum\s+(?:rating\s+(?:of\s+)?)?([\d.]+)',
    ]
    for pat in patterns:
        m = re.search(pat, instruction, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 0 < val <= 5:
                return val
    return 0.0


def _extract_variants(instruction: str) -> List[str]:
    """
    Extract product variants mentioned in instruction.
    e.g. "256GB", "Blue", "XL", "iPhone 16 Pro Max 512GB Black"
    """
    variants = []
    # Storage variants
    storage = re.findall(r'\b(\d+\s*(?:GB|TB|MB))\b', instruction, re.IGNORECASE)
    variants.extend([s.replace(" ", "") for s in storage])
    # Color variants
    colors = re.findall(
        r'\b(black|white|blue|red|green|yellow|purple|pink|silver|gold|gray|grey|'
        r'midnight|starlight|titanium|natural)\b',
        instruction, re.IGNORECASE
    )
    variants.extend([c.title() for c in colors])
    # Size variants (clothing/accessories)
    sizes = re.findall(r'\b(XS|S|M|L|XL|XXL|2XL|3XL|small|medium|large|extra\s+large)\b', instruction, re.IGNORECASE)
    variants.extend(sizes)
    # RAM
    ram = re.findall(r'\b(\d+\s*(?:RAM|GB\s+RAM))\b', instruction, re.IGNORECASE)
    variants.extend(ram)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for v in variants:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique


def _extract_product_index(instruction: str) -> Optional[int]:
    """Extract result index from instruction."""
    # Check ordinal words first
    ordinal_map = {
        'first': 1, '1st': 1,
        'second': 2, '2nd': 2,
        'third': 3, '3rd': 3,
        'fourth': 4, '4th': 4,
        'fifth': 5, '5th': 5,
        'sixth': 6, '6th': 6,
        'seventh': 7, '7th': 7,
        'eighth': 8, '8th': 8,
        'ninth': 9, '9th': 9,
        'tenth': 10, '10th': 10,
    }
    
    il = instruction.lower()
    for word, num in ordinal_map.items():
        if re.search(rf'\b{word}\b\s+(?:product|result|item|listing)', il):
            return num
    
    # Check numeric patterns
    patterns = [
        r'(\d+)(?:st|nd|rd|th)\s+(?:product|result|item|listing)',
        r'(?:product|result|item|listing)\s+(?:number\s+|#\s*)?(\d+)\b',
        r'#(\d+)\s+(?:product|result)',
    ]
    
    for pat in patterns:
        m = re.search(pat, instruction, re.IGNORECASE)
        if m:
            return int(m.group(1))
    
    return None


def _extract_google_image_index(instruction: str) -> int:
    """Extract which Google image to click."""
    ordinal_map = {
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        '1st': 1, '2nd': 2, '3rd': 3,
    }
    il = instruction.lower()
    for word, num in ordinal_map.items():
        if word in il:
            return num
    m = re.search(r'(\d+)(?:st|nd|rd|th)?\s+(?:image|photo|picture|result)', il)
    if m:
        return int(m.group(1))
    return 1


def _detect_sort_type(instruction: str) -> Optional[str]:
    """Return sort type from keywords."""
    il = instruction.lower()
    if any(k in il for k in ["cheapest", "lowest price", "low to high", "budget", "affordable"]):
        return "price_low_to_high"
    if any(k in il for k in ["most expensive", "highest price", "high to low", "premium", "luxury"]):
        return "price_high_to_low"
    if any(k in il for k in ["best rated", "top rated", "highest rated", "most popular", "best review"]):
        return "rating"
    if any(k in il for k in ["newest", "latest", "new arrival", "recently added"]):
        return "newest"
    return None


def _is_compound_smart_query(instruction: str) -> bool:
    """Detect instructions like 'find X under ₹Y with rating above Z and add best to cart'."""
    il = instruction.lower()
    has_price = _extract_max_price(instruction) is not None
    has_rating = _extract_min_rating(instruction) > 0
    has_cart = any(k in il for k in ["add to cart", "add best", "add it", "buy best", "purchase best"])
    return (has_price or has_rating) and has_cart


def _extract_monitor_info(instruction: str) -> Dict:
    """
    Parse monitoring instructions like:
    "If Tesla stock drops 5%, buy 100 shares."
    "If PS5 goes below ₹45000, buy automatically."
    "Monitor Bitcoin and sell when price increases 8%."
    """
    il = instruction.lower()
    info = {
        "type": "crypto",
        "id": "bitcoin",
        "condition": "below",
        "threshold": 50000,
        "action": "notify",
        "interval": 30,
        "platform": "amazon",
        "product_url": None,
    }

    # Item type detection
    stock_keywords = ["stock", "share", "equity", "nasdaq", "nyse"]
    if any(k in il for k in stock_keywords):
        info["type"] = "stock"
    elif any(k in il for k in ["amazon", "flipkart", "product", "item", "ps5", "laptop", "phone"]):
        info["type"] = "ecommerce"
    else:
        info["type"] = "crypto"

    # Platform
    if "flipkart" in il:
        info["platform"] = "flipkart"

    # Condition: percent-based
    drop_match = re.search(r'drops?\s*(\d+(?:\.\d+)?)\s*%', il)
    rise_match = re.search(r'(?:rise|increase|goes?\s+up)\s*(\d+(?:\.\d+)?)\s*%', il)
    below_match = re.search(r'(?:below|under|less\s+than|drops?\s+to)\s*[₹$]?\s*([\d,]+)', il)
    above_match = re.search(r'(?:above|over|more\s+than|rises?\s+to)\s*[₹$]?\s*([\d,]+)', il)

    if drop_match:
        info["condition"] = "drops_percent"
        info["threshold"] = float(drop_match.group(1))
    elif rise_match:
        info["condition"] = "rises_percent"
        info["threshold"] = float(rise_match.group(1))
    elif below_match:
        info["condition"] = "below"
        info["threshold"] = float(below_match.group(1).replace(",", ""))
    elif above_match:
        info["condition"] = "above"
        info["threshold"] = float(above_match.group(1).replace(",", ""))

    # Action
    if any(k in il for k in ["buy", "purchase", "add to cart"]):
        info["action"] = "buy_now" if "buy" in il else "add_to_cart"
    elif any(k in il for k in ["sell"]):
        info["action"] = "notify"  # Can extend for sell orders

    # Item ID
    # Crypto
    crypto_map = {
        "bitcoin": "bitcoin", "btc": "bitcoin",
        "ethereum": "ethereum", "eth": "ethereum",
        "solana": "solana", "sol": "solana",
        "dogecoin": "dogecoin", "doge": "dogecoin",
    }
    for key, val in crypto_map.items():
        if key in il:
            info["id"] = val
            break

    # Stock tickers
    stock_m = re.search(r'\b([A-Z]{1,5})\b\s+stock', instruction)
    if stock_m:
        info["id"] = stock_m.group(1)

    # Product names (for ecommerce)
    product_keywords = ["ps5", "playstation 5", "laptop", "iphone", "macbook", "airpods"]
    for pk in product_keywords:
        if pk in il:
            info["id"] = pk
            break

    # Interval
    interval_m = re.search(r'every\s+(\d+)\s*(second|minute|hour)', il)
    if interval_m:
        val = int(interval_m.group(1))
        unit = interval_m.group(2)
        info["interval"] = val if "second" in unit else val * 60 if "minute" in unit else val * 3600

    return info


# ─────────────────────────────────────────────
# LLM Service
# ─────────────────────────────────────────────
class LLMService:

    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL
        self.model = config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS
        self._rag = get_rag_store()

    # ── Intent Detection ─────────────────────────────────────────────
    def _detect_intent(self, instruction: str) -> str:
        il = instruction.lower()
        if "amazon" in il or ("cart" in il and "amazon" not in il and "flipkart" not in il):
            return "amazon"
        if "flipkart" in il:
            return "flipkart"
        if "youtube" in il or "video" in il:
            return "youtube"
        if any(k in il for k in ["monitor", "track price", "buy if", "notify if", "sell when", "alert when", "drops", "rises", "goes below", "goes above"]):
            return "monitoring"
        if any(k in il for k in ["google image", "image search", "download image", "download photo", "find image"]):
            return "google_images"
        if any(k in il for k in ["flight", "fly", "airline", "ticket"]):
            return "flights"
        if any(k in il for k in ["login", "sign in", "log in"]):
            return "login_no_url"
        return "google_search"

    # ── Amazon Plan Builder ──────────────────────────────────────────
    def _plan_amazon_search(self, instruction: str) -> Dict:
        query = _extract_search_term(instruction)
        il = instruction.lower()
        steps = []

        # ── Step 1: Search ──
        steps.append({
            "action": "search",
            "query": query,
            "platform": "amazon",
            "original_instruction": instruction,
            "description": f"Search Amazon for '{query}'",
        })

        # ── Step 2: Auto-sort from keyword ──
        sort_type = _detect_sort_type(instruction)
        if sort_type:
            steps.append({
                "action": "apply_sort",
                "sort_type": sort_type,
                "platform": "amazon",
                "description": f"Sort by {sort_type.replace('_', ' ')}",
            })

        # ── Step 3: Price filter ──
        max_price = _extract_max_price(instruction)
        if max_price:
            steps.append({
                "action": "apply_price_filter",
                "max_price": max_price,
                "min_price": 0,
                "platform": "amazon",
                "description": f"Filter price under ₹{max_price:,.0f}",
            })

        # ── Step 4: Rating filter ──
        min_rating = _extract_min_rating(instruction)
        if min_rating > 0:
            steps.append({
                "action": "apply_rating_filter",
                "min_rating": min_rating,
                "platform": "amazon",
                "description": f"Filter rating ≥ {min_rating}★",
            })

        # ── Smart compound query: find best + add to cart ──
        if _is_compound_smart_query(instruction):
            steps.append({
                "action": "smart_find_and_add_best",
                "max_price": max_price,
                "min_rating": min_rating or 0,
                "platform": "amazon",
                "limit": 20,
                "description": f"Find best product under ₹{max_price} with ≥{min_rating}★ and add to cart",
            })
            self._print_plan("AMAZON (SMART)", steps)
            return {"steps": steps, "_source": "modular_amazon_smart"}

        # ── Product click by index ──
        product_index = _extract_product_index(instruction)
        if product_index:
            steps.append({
                "action": "click_product_index",
                "index": product_index,
                "platform": "amazon",
                "description": f"Click product #{product_index}",
            })
        else:
            # Product click by name
            name_m = re.search(
                r'(?:open|click|view|show|find|check)\s+(?:the\s+)?(.+?)(?:\s+on\s+amazon|$)',
                instruction, re.IGNORECASE
            )
            if name_m:
                product_name = name_m.group(1).strip()
                # Don't use name if it's just the search query
                if product_name.lower() != query.lower():
                    steps.append({
                        "action": "click_product_name",
                        "product_name": product_name,
                        "platform": "amazon",
                        "description": f"Click product: {product_name}",
                    })

        # ── Variant selection ──
        variants = _extract_variants(instruction)
        for variant in variants:
            steps.append({
                "action": "select_variant",
                "variant": variant,
                "platform": "amazon",
                "description": f"Select variant: {variant}",
            })

        # ── Quantity ──
        quantity = _extract_quantity(instruction)

        # ── Add to cart / Buy now ──
        if "add to cart" in il or "add to cart" in il:
            steps.append({
                "action": "add_to_cart",
                "platform": "amazon",
                "quantity": quantity,
                "description": f"Add to cart (qty={quantity})",
            })
        elif "buy now" in il or "buy it now" in il:
            steps.append({
                "action": "buy_now",
                "platform": "amazon",
                "quantity": quantity,
                "description": f"Buy Now (qty={quantity})",
            })

        # ── Scroll ──
        if "scroll down" in il:
            steps.append({"action": "scroll", "direction": "down", "amount": 1000, "description": "Scroll down"})
        elif "scroll up" in il:
            steps.append({"action": "scroll", "direction": "up", "amount": 1000, "description": "Scroll up"})

        self._print_plan("AMAZON", steps)
        return {"steps": steps, "_source": "modular_amazon"}

    # ── Flipkart Plan Builder ────────────────────────────────────────
    def _plan_flipkart_search(self, instruction: str) -> Dict:
        query = _extract_search_term(instruction)
        il = instruction.lower()
        steps = []

        steps.append({
            "action": "search",
            "query": query,
            "platform": "flipkart",
            "original_instruction": instruction,
            "description": f"Search Flipkart for '{query}'",
        })

        sort_type = _detect_sort_type(instruction)
        if sort_type:
            steps.append({
                "action": "apply_sort",
                "sort_type": sort_type,
                "platform": "flipkart",
                "description": f"Sort by {sort_type.replace('_', ' ')}",
            })

        max_price = _extract_max_price(instruction)
        if max_price:
            steps.append({
                "action": "apply_price_filter",
                "max_price": max_price,
                "platform": "flipkart",
                "description": f"Filter price ≤ ₹{max_price:,.0f}",
            })

        min_rating = _extract_min_rating(instruction)
        if min_rating > 0:
            steps.append({
                "action": "apply_rating_filter",
                "min_rating": min_rating,
                "platform": "flipkart",
                "description": f"Filter rating ≥ {min_rating}★",
            })

        if _is_compound_smart_query(instruction):
            steps.append({
                "action": "smart_find_and_add_best",
                "max_price": max_price,
                "min_rating": min_rating or 0,
                "platform": "flipkart",
                "limit": 20,
                "description": "Find best product and add to cart",
            })
            self._print_plan("FLIPKART (SMART)", steps)
            return {"steps": steps, "_source": "modular_flipkart_smart"}

        product_index = _extract_product_index(instruction)
        if product_index:
            steps.append({
                "action": "click_product_index",
                "index": product_index,
                "platform": "flipkart",
                "description": f"Click product #{product_index}",
            })
        else:
            name_m = re.search(
                r'(?:open|click|view|find)\s+(?:the\s+)?(.+?)(?:\s+on\s+flipkart|$)',
                instruction, re.IGNORECASE
            )
            if name_m:
                pname = name_m.group(1).strip()
                if pname.lower() != query.lower():
                    steps.append({
                        "action": "click_product_name",
                        "product_name": pname,
                        "platform": "flipkart",
                        "description": f"Click product: {pname}",
                    })

        variants = _extract_variants(instruction)
        for variant in variants:
            steps.append({
                "action": "select_variant",
                "variant": variant,
                "platform": "flipkart",
                "description": f"Select variant: {variant}",
            })

        quantity = _extract_quantity(instruction)

        if "add to cart" in il:
            steps.append({
                "action": "add_to_cart",
                "platform": "flipkart",
                "quantity": quantity,
                "description": f"Add to cart (qty={quantity})",
            })
        elif "buy now" in il:
            steps.append({
                "action": "buy_now",
                "platform": "flipkart",
                "quantity": quantity,
                "description": f"Buy Now (qty={quantity})",
            })

        if "scroll down" in il:
            steps.append({"action": "scroll", "direction": "down", "amount": 1000, "description": "Scroll down"})

        self._print_plan("FLIPKART", steps)
        return {"steps": steps, "_source": "modular_flipkart"}

    # ── YouTube Plan Builder ─────────────────────────────────────────
    def _plan_youtube(self, instruction: str) -> Dict:
        query = _extract_search_term(instruction)
        il = instruction.lower()

        steps = [
            {
                "action": "youtube_search",
                "query": query,
                "skip_shorts": True,
                "description": f"Search and play: {query}",
            }
        ]

        interaction_map = {
            "like": ["like the video", "like it", "give a like", "thumbs up"],
            "fullscreen": ["fullscreen", "full screen", "maximize"],
            "open_comments": ["comment", "open comment", "view comment"],
            "subscribe": ["subscribe", "subscription"],
            "mute": ["mute", "mute the video"],
            "pause": ["pause", "stop"],
            "scroll_comments": ["scroll comment"],
            "settings": ["settings", "quality", "playback speed"],
        }

        for interaction, keywords in interaction_map.items():
            if any(k in il for k in keywords):
                steps.append({
                    "action": "youtube_interact",
                    "interaction": interaction,
                    "description": f"YouTube: {interaction}",
                })

        self._print_plan("YOUTUBE", steps)
        return {"steps": steps, "_source": "direct_youtube"}

    # ── Google Images Plan Builder ───────────────────────────────────
    def _plan_google_images(self, instruction: str) -> Dict:
        query = _extract_search_term(instruction)
        if not query or query == "search":
            # Extract query from context
            m = re.search(
                r'(?:search|find|download|get)\s+(?:an?\s+)?(?:image|photo|picture)\s+(?:of\s+)?(.+?)(?:\s+from|$)',
                instruction, re.IGNORECASE
            )
            if m:
                query = m.group(1).strip()

        img_index = _extract_google_image_index(instruction)
        il = instruction.lower()

        steps = [
            {
                "action": "search_images",
                "query": query,
                "description": f"Search Google Images for '{query}'",
            },
            {
                "action": "click_google_image",
                "index": img_index,
                "description": f"Click image #{img_index}",
            },
        ]

        if any(k in il for k in ["download", "save", "high res", "high-res", "full size"]):
            steps.append({
                "action": "download_highres",
                "description": "Download high-resolution image",
            })

        self._print_plan("GOOGLE IMAGES", steps)
        return {"steps": steps, "_source": "direct_images"}

    # ── Monitoring Plan Builder ──────────────────────────────────────
    def _plan_monitoring(self, instruction: str) -> Dict:
        info = _extract_monitor_info(instruction)

        steps = [
            {
                "action": "start_monitoring",
                "monitors": [{
                    "type": info["type"],
                    "id": info["id"],
                    "condition": info["condition"],
                    "threshold": info["threshold"],
                    "action": info["action"],
                    "platform": info["platform"],
                    "product_url": info["product_url"],
                    "interval": info["interval"],
                }],
                "description": (
                    f"Monitor {info['id']}: {info['condition']} {info['threshold']} "
                    f"→ {info['action']} (every {info['interval']}s)"
                ),
            },
            {
                "action": "check_monitors",
                "description": "Check monitor status",
            },
        ]

        self._print_plan("MONITORING", steps)
        return {"steps": steps, "_source": "direct_monitoring"}

    # ── Flights Plan Builder ─────────────────────────────────────────
    def _plan_flights(self, instruction: str) -> Dict:
        origin_m = re.search(r'from\s+([A-Z]{3}|\w+)', instruction, re.IGNORECASE)
        dest_m = re.search(r'to\s+([A-Z]{3}|\w+)', instruction, re.IGNORECASE)
        origin = origin_m.group(1).upper() if origin_m else "DEL"
        dest = dest_m.group(1).upper() if dest_m else "BOM"
        steps = [{
            "action": "compare_flights",
            "origin": origin,
            "destination": dest,
            "description": f"Compare flights {origin} → {dest}",
        }]
        self._print_plan("FLIGHTS", steps)
        return {"steps": steps, "_source": "direct_flights"}

    # ── Login Plan Builder ───────────────────────────────────────────
    def _plan_login(self, url: str, instruction: str) -> Dict:
        username, password = _extract_credentials(instruction)
        # OTP secret
        otp_m = re.search(r'otp[_\s]secret[:\s]+([A-Z2-7]{16,})', instruction, re.IGNORECASE)
        otp_secret = otp_m.group(1) if otp_m else None

        steps = [
            {"action": "navigate", "url": url, "description": f"Navigate to {url}"},
            {
                "action": "smart_login",
                "username": username,
                "password": password,
                "otp_secret": otp_secret,
                "description": f"Login as {username}",
            },
        ]
        self._print_plan("LOGIN", steps)
        return {"steps": steps, "_source": "direct_login"}

    def _plan_generic_url(self, url: str, instruction: str) -> Dict:
        query = _extract_search_term(instruction)
        steps = [
            {"action": "navigate", "url": url, "description": f"Navigate to {url}"},
            {"action": "fill", "selector": "input[type='search'], input[name='q'], textarea[name='q']", "value": query},
            {"action": "press", "key": "Enter"},
        ]
        self._print_plan("GENERIC URL", steps)
        return {"steps": steps, "_source": "direct_generic"}

    # ── Main Entry Point ─────────────────────────────────────────────
    def generate_test_steps(self, user_instruction: str, force_fresh: bool = False) -> Dict:
        detected_url = _extract_url(user_instruction)
        if detected_url:
            logger.info(f"[LLMService] URL detected: {detected_url}")
            plan = self._build_url_plan(user_instruction, detected_url)
            plan, issues = validate_and_repair_plan(plan, user_instruction)
            return {
                "success": True,
                "test_plan": plan,
                "error": None,
                "was_repaired": bool(issues),
                "validation_issues": issues,
                "bypassed_llm": True,
                "bypassed_rag": True,
            }

        intent = self._detect_intent(user_instruction)
        logger.info(f"[LLMService] Intent='{intent}'")

        if intent == "amazon":
            plan = self._plan_amazon_search(user_instruction)
        elif intent == "flipkart":
            plan = self._plan_flipkart_search(user_instruction)
        elif intent == "youtube":
            plan = self._plan_youtube(user_instruction)
        elif intent == "monitoring":
            plan = self._plan_monitoring(user_instruction)
        elif intent == "google_images":
            plan = self._plan_google_images(user_instruction)
        elif intent == "flights":
            plan = self._plan_flights(user_instruction)
        elif intent == "login_no_url":
            plan = self._plan_login("https://www.google.com", user_instruction)
        else:
            plan = self._llm_plan(user_instruction, force_fresh)

        plan, issues = validate_and_repair_plan(plan, user_instruction)

        print("\n" + "=" * 70)
        print("📋 FINAL GENERATED PLAN:")
        for i, step in enumerate(plan.get("steps", []), 1):
            desc = step.get("description", "")
            print(f"  Step {i:>2}: [{step.get('action')}]  {desc[:65]}")
        print("=" * 70 + "\n")

        return {
            "success": True,
            "test_plan": plan,
            "error": None,
            "was_repaired": bool(issues),
            "validation_issues": issues,
        }

    def _build_url_plan(self, instruction: str, url: str) -> Dict:
        if "amazon" in url.lower():
            return self._plan_amazon_search(instruction)
        if "flipkart" in url.lower():
            return self._plan_flipkart_search(instruction)
        if "youtube" in url.lower():
            return self._plan_youtube(instruction)
        if any(k in instruction.lower() for k in ["monitor", "buy if"]):
            return self._plan_monitoring(instruction)
        if any(k in instruction.lower() for k in ["image", "photo"]):
            return self._plan_google_images(instruction)
        if "flight" in instruction.lower():
            return self._plan_flights(instruction)
        if any(k in instruction.lower() for k in ["login", "sign in"]):
            return self._plan_login(url, instruction)
        return self._plan_generic_url(url, instruction)

    # ── LLM Fallback ─────────────────────────────────────────────────
    def _llm_plan(self, instruction: str, force_fresh: bool) -> Dict:
        rag = self._rag
        if not force_fresh:
            rag_steps, _ = rag.find_similar_workflow_parameterized(instruction, force_fresh=False)
            if rag_steps:
                logger.info("[LLMService] Using RAG workflow")
                return {"steps": rag_steps, "_source": "rag"}

        rag_ctx = rag.get_context_for_prompt(instruction, force_fresh=force_fresh)
        prompt = self._build_prompt(instruction, rag_ctx)

        try:
            raw = self._call_ollama(prompt)
            plan, _ = debug_agent.fix_test_plan(raw, instruction=instruction)
            if plan:
                plan = self._override_search_term(plan, instruction)
                return plan
        except Exception as e:
            logger.error(f"LLM call failed: {e}")

        query = _extract_search_term(instruction)
        return {
            "steps": [
                {"action": "navigate", "url": "https://www.google.com"},
                {"action": "fill", "selector": "textarea[name='q']", "value": query},
                {"action": "press", "key": "Enter"},
            ],
            "_source": "fallback",
        }

    def _override_search_term(self, plan: Dict, instruction: str) -> Dict:
        new_term = _extract_search_term(instruction)
        if not new_term:
            return plan
        for step in plan.get("steps", []):
            if step.get("action") in ["search", "search_products", "search_images", "youtube_search"]:
                step["query"] = new_term
            if step.get("action") == "fill" and any(
                k in step.get("selector", "").lower() for k in ["search", "q"]
            ):
                step["value"] = new_term
        return plan

    def _call_ollama(
        self, prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature if temperature is not None else self.temperature,
                    "num_predict": max_tokens or self.max_tokens,
                },
            },
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _build_prompt(self, instruction: str, rag_context: str = "") -> str:
        rag_section = f"\nCONTEXT:\n{rag_context}\n" if rag_context else ""
        return f"""Convert to JSON test plan.

Instruction: "{instruction}"
{rag_section}
VALID ACTIONS:
  navigate, click, fill, press, wait, assert, scroll, type
  search, apply_sort, apply_price_filter, apply_rating_filter
  click_product_index, click_product_name
  select_variant, select_quantity
  add_to_cart, buy_now, get_products, smart_find_and_add_best
  search_images, click_google_image, download_highres
  youtube_search, youtube_interact
  smart_login, compare_flights
  start_monitoring, check_monitors, stop_monitoring

Output: {{"steps": [{{"action": "...", "description": "..."}}]}}

Return ONLY valid JSON.
JSON:"""

    def fix_selector_via_llm(self, failed_step: Dict, error_message: str) -> Optional[str]:
        prompt = (
            f"Suggest ONE better CSS selector.\n"
            f"Action: {failed_step.get('action')}\n"
            f"Error: {error_message}\n"
            f"Selector:"
        )
        try:
            raw = self._call_ollama(prompt, max_tokens=60, temperature=0.0).strip().strip('"\'`')
            if raw and len(raw) < 200:
                return raw
        except Exception:
            pass
        return None

    def health_check(self) -> bool:
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": "ping", "stream": False, "options": {"num_predict": 1}},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _print_plan(self, plan_type: str, steps: List[Dict]):
        print("\n" + "=" * 70)
        print(f"📋 {plan_type} PLAN")
        print("=" * 70)
        for i, step in enumerate(steps, 1):
            print(f"  Step {i:>2}: [{step.get('action')}]  {step.get('description', '')[:65]}")
        print("=" * 70 + "\n")


llm_service = LLMService()
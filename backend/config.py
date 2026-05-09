"""
Configuration — Complete Production Configuration v10.0
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
REPORTS_DIR = BASE_DIR / "reports"
RAG_DATA_DIR = BASE_DIR / "rag_data"
SESSIONS_DIR = BASE_DIR / "sessions"
DOWNLOADS_DIR = BASE_DIR / "downloads"

for d in (SCREENSHOTS_DIR, REPORTS_DIR, RAG_DATA_DIR, SESSIONS_DIR, DOWNLOADS_DIR):
    d.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
API_BASE_URL = os.getenv("API_BASE_URL", f"http://localhost:{PORT}")

# ---------------------------------------------------------------------------
# LLM (Ollama)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", "")

# ---------------------------------------------------------------------------
# Browser / Playwright
# ---------------------------------------------------------------------------
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30000"))
VIEWPORT_WIDTH = int(os.getenv("VIEWPORT_WIDTH", "1280"))
VIEWPORT_HEIGHT = int(os.getenv("VIEWPORT_HEIGHT", "720"))

NAVIGATION_TIMEOUT = int(os.getenv("NAVIGATION_TIMEOUT", "40000"))
AMAZON_TIMEOUT = int(os.getenv("AMAZON_TIMEOUT", "30000"))
FLIPKART_TIMEOUT = int(os.getenv("FLIPKART_TIMEOUT", "25000"))
YOUTUBE_TIMEOUT = int(os.getenv("YOUTUBE_TIMEOUT", "20000"))
FLIGHT_TIMEOUT = int(os.getenv("FLIGHT_TIMEOUT", "30000"))
MONITOR_TIMEOUT = int(os.getenv("MONITOR_TIMEOUT", "15000"))

# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
STEP_DELAY = int(os.getenv("STEP_DELAY", "1000"))
SLOW_MO = int(os.getenv("SLOW_MO", "200"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "50"))
STEP_EXECUTION_TIMEOUT = int(os.getenv("STEP_EXECUTION_TIMEOUT", "120"))
INTER_ACTION_DELAY = int(os.getenv("INTER_ACTION_DELAY", "500"))

# ---------------------------------------------------------------------------
# Planning / Replanning
# ---------------------------------------------------------------------------
MAX_REPLAN_ATTEMPTS = int(os.getenv("MAX_REPLAN_ATTEMPTS", "5"))
ENABLE_FEEDBACK_LOOP = os.getenv("ENABLE_FEEDBACK_LOOP", "True").lower() == "true"
REPLAN_FAILURE_THRESHOLD = int(os.getenv("REPLAN_FAILURE_THRESHOLD", "3"))
VISUAL_VERIFICATION_ENABLED = os.getenv("VISUAL_VERIFICATION_ENABLED", "True").lower() == "true"

# ---------------------------------------------------------------------------
# Decision Engine
# ---------------------------------------------------------------------------
DECISION_PRICE_WEIGHT = float(os.getenv("DECISION_PRICE_WEIGHT", "0.40"))
DECISION_RATING_WEIGHT = float(os.getenv("DECISION_RATING_WEIGHT", "0.35"))
DECISION_REVIEW_WEIGHT = float(os.getenv("DECISION_REVIEW_WEIGHT", "0.15"))
DECISION_KEYWORD_WEIGHT = float(os.getenv("DECISION_KEYWORD_WEIGHT", "0.10"))
DECISION_DURATION_WEIGHT = float(os.getenv("DECISION_DURATION_WEIGHT", "0.30"))

# ---------------------------------------------------------------------------
# Monitoring Engine
# ---------------------------------------------------------------------------
MONITOR_DEFAULT_POLL_INTERVAL = int(os.getenv("MONITOR_DEFAULT_POLL_INTERVAL", "30"))
MONITOR_MIN_POLL_INTERVAL = int(os.getenv("MONITOR_MIN_POLL_INTERVAL", "10"))
MONITOR_MAX_CONCURRENT = int(os.getenv("MONITOR_MAX_CONCURRENT", "50"))
MONITOR_MAX_CHECKS = int(os.getenv("MONITOR_MAX_CHECKS", "2880"))
MONITOR_AUTO_START = os.getenv("MONITOR_AUTO_START", "True").lower() == "true"
MONITOR_ENABLE_ACTIONS = os.getenv("MONITOR_ENABLE_ACTIONS", "True").lower() == "true"

MONITOR_TYPES = ["stock", "crypto", "ecommerce"]
MONITOR_CONDITIONS = ["below", "above", "drops_percent", "rises_percent"]

CRYPTO_API_URL = "https://api.coingecko.com/api/v3/simple/price"
STOCK_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

# ---------------------------------------------------------------------------
# Vision Engine
# ---------------------------------------------------------------------------
VISION_ENABLED = os.getenv("VISION_ENABLED", "True").lower() == "true"
VISION_OCR_BACKEND = os.getenv("VISION_OCR_BACKEND", "tesseract")
VISION_DIFF_ENABLED = os.getenv("VISION_DIFF_ENABLED", "True").lower() == "true"
VISION_MIN_CONFIDENCE = float(os.getenv("VISION_MIN_CONFIDENCE", "0.60"))
VISION_MAX_SCREENSHOT_BYTES = int(os.getenv("VISION_MAX_SCREENSHOT_BYTES", "500000"))
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")

# ---------------------------------------------------------------------------
# Platform-Specific Selectors
# ---------------------------------------------------------------------------
AMAZON_SELECTORS = {
    "search_box": "#twotabsearchtextbox",
    "search_button": "#nav-search-submit-button",
    "product_results": "div[data-component-type='s-search-result']",
    "product_title": "h2 a",
    "product_price": ".a-price .a-offscreen",
    "product_rating": ".a-icon-alt",
    "add_to_cart": "#add-to-cart-button",
    "cart_count": "#nav-cart-count",
    "buy_now": "#buy-now-button",
    "quantity_dropdown": "select#quantity",
    "quantity_input": "input#quantity",
    "sort_dropdown": "select#s-result-sort-select",
    "next_page": "a.s-pagination-next",
    "variants": [
        "div#variation_size_name",
        "div#variation_color_name",
        "div#variation_style_name",
        "select[name='dropdown_selected_size_name']",
    ],
}

FLIPKART_SELECTORS = {
    "search_box": "input._2P_LnL",
    "search_button": "button._2i2sHZ",
    "product_results": "div._1AtVbE",
    "product_title": "a._1fQZEK",
    "product_price": "div._30jeq3",
    "product_rating": "div._3LWZlK",
    "add_to_cart": "button._2KpZ6l",
    "buy_now": "button._2KpZ6l._2U9uOA",
    "close_popup": "button._2KpZ6l._2doB4z",
    "next_page": "a._1LKTO3",
    "sort_button": "div._2sDqCO button",
}

GOOGLE_IMAGES_SELECTORS = {
    "images_tab": "a[href*='tbm=isch']",
    "thumbnail": "div[data-ri], img.Q4LuWd, img.rg_i",
    "highres_image": "img.n3VNCb, img.iPVvYb",
}

YOUTUBE_SELECTORS = {
    "search_box": "input#search",
    "search_button": "button#search-icon-legacy",
    "video_thumbnail": "#dismissible ytd-video-renderer a#thumbnail",
    "like_button": "button[aria-label*='like this video']",
    "fullscreen": "button.ytp-fullscreen-button",
    "settings": "button.ytp-settings-button",
    "comments_section": "#comments",
    "subscribe": "ytd-subscribe-button-renderer button",
    "mute": "button.ytp-mute-button",
    "play_pause": "button.ytp-play-button",
}

FLIGHT_SELECTORS = {
    "makemytrip_origin": "input[placeholder*='From']",
    "makemytrip_destination": "input[placeholder*='To']",
    "makemytrip_date": "input[placeholder*='Departure']",
    "makemytrip_search": "button[class*='search']",
}

LOGIN_SELECTORS = {
    "username": [
        "input[type='email']",
        "input[name*='email']",
        "input[name*='username']",
        "input[placeholder*='Email' i]",
        "input[placeholder*='Username' i]",
        "#email", "#username",
    ],
    "password": [
        "input[type='password']",
        "input[name*='password']",
        "input[placeholder*='Password' i]",
        "#password", "#passwd",
    ],
    "submit": [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Sign in')",
        "#loginButton", "#signInButton",
    ],
    "next": [
        "button:has-text('Next')",
        "button:has-text('Continue')",
        "input[value='Next']",
    ],
}

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "15"))
WS_MAX_CONNECTIONS = int(os.getenv("WS_MAX_CONNECTIONS", "50"))
WS_LIVE_STEPS = os.getenv("WS_LIVE_STEPS", "True").lower() == "true"

# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------
RAG_BACKEND = os.getenv("RAG_BACKEND", "auto")
RAG_EMBEDDINGS = os.getenv("RAG_EMBEDDINGS", "auto")
RAG_FORCE_FRESH_DEFAULT = os.getenv("RAG_FORCE_FRESH_DEFAULT", "false").lower() == "true"
RAG_MIN_SIMILARITY = float(os.getenv("RAG_MIN_SIMILARITY", "0.75"))
RAG_MAX_WORKFLOW_STORE = int(os.getenv("RAG_MAX_WORKFLOW_STORE", "200"))

# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
SCREENSHOT_DIR = SCREENSHOTS_DIR

# ---------------------------------------------------------------------------
# API / CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS = [
    "http://localhost:8080", "http://localhost:3000",
    "http://127.0.0.1:8080", "http://127.0.0.1:3000",
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost:8501", "http://127.0.0.1:8501",
    "http://localhost:5500", "http://127.0.0.1:5500",
    "http://localhost:5173", "http://127.0.0.1:5173",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
LOG_FILE = os.getenv("LOG_FILE", "")
LOG_ROTATION_DAYS = int(os.getenv("LOG_ROTATION_DAYS", "7"))

# ---------------------------------------------------------------------------
# Misc / Cleanup
# ---------------------------------------------------------------------------
MAX_CONCURRENT_TESTS = int(os.getenv("MAX_CONCURRENT_TESTS", "1"))
TEST_CLEANUP_DAYS = int(os.getenv("TEST_CLEANUP_DAYS", "7"))
DEFAULT_NAVIGATE_URL = "https://www.google.com"

# ── VALID_ACTIONS ── single source of truth used by engine, debug_agent, step_schema
VALID_ACTIONS = [
    # Basic browser
    "navigate", "click", "fill", "press", "wait",
    "assert", "download", "scroll", "hover", "select", "extract", "type",

    # Ecommerce: search & sort/filter
    "search",
    "apply_sort",
    "auto_sort",
    "apply_price_filter",
    "apply_rating_filter",

    # Ecommerce: product navigation
    "click_product_index",
    "click_product_name",

    # Ecommerce: variants, quantity, cart
    "select_variant",
    "select_quantity",
    "add_to_cart",
    "buy_now",
    "get_products",
    "smart_find_and_add_best",

    # Google Images
    "search_images",
    "click_google_image",
    "download_highres",

    # YouTube
    "youtube_search",
    "youtube_interact",

    # Login
    "smart_login",

    # Flights
    "compare_flights",

    # Monitoring
    "start_monitoring",
    "check_monitors",
    "stop_monitoring",

    # Human-in-the-loop
    "request_human_input",
    "provide_human_input",

    # Legacy (kept for RAG workflow compatibility)
    "search_products",
]

# ---------------------------------------------------------------------------
# Site Configurations
# ---------------------------------------------------------------------------
SITE_CONFIGS = {
    "amazon": {
        "base_url": "https://www.amazon.in",
        "timeout": AMAZON_TIMEOUT,
        "slow_mo_extra": 200,
    },
    "flipkart": {
        "base_url": "https://www.flipkart.com",
        "timeout": FLIPKART_TIMEOUT,
        "slow_mo_extra": 150,
    },
    "youtube": {
        "base_url": "https://www.youtube.com",
        "timeout": YOUTUBE_TIMEOUT,
        "slow_mo_extra": 0,
    },
}

# ---------------------------------------------------------------------------
# Geographic defaults
# ---------------------------------------------------------------------------
GEO_LATITUDE = float(os.getenv("GEO_LATITUDE", "12.9716"))
GEO_LONGITUDE = float(os.getenv("GEO_LONGITUDE", "77.5946"))
LOCALE = os.getenv("LOCALE", "en-US")
TIMEZONE_ID = os.getenv("TIMEZONE_ID", "Asia/Kolkata")

# ---------------------------------------------------------------------------
# Browser arguments
# ---------------------------------------------------------------------------
CHROME_ARGS = [
    "--start-maximized",
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
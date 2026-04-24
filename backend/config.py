"""
Configuration — AI Testing Agent
All original settings preserved; RAG and Streamlit additions appended at the bottom.
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

for d in (SCREENSHOTS_DIR, REPORTS_DIR, RAG_DATA_DIR):
    d.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Convenience alias used by streamlit_app.py
API_BASE_URL = os.getenv("API_BASE_URL", f"http://localhost:{PORT}")

# ---------------------------------------------------------------------------
# LLM (Ollama)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

# ---------------------------------------------------------------------------
# Browser / Playwright
# ---------------------------------------------------------------------------
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30000"))   # ms
VIEWPORT_WIDTH = int(os.getenv("VIEWPORT_WIDTH", "1280"))
VIEWPORT_HEIGHT = int(os.getenv("VIEWPORT_HEIGHT", "720"))

# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
STEP_DELAY = int(os.getenv("STEP_DELAY", "1000"))  # ms between steps

# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------
RAG_BACKEND = os.getenv("RAG_BACKEND", "auto")        # "chromadb" | "json" | "auto"
RAG_EMBEDDINGS = os.getenv("RAG_EMBEDDINGS", "auto")  # "sentence_transformers" | "none" | "auto"

# When True the system ALWAYS generates a fresh plan (no RAG workflow reuse).
# Individual API calls can override this per-request via the force_fresh field.
RAG_FORCE_FRESH_DEFAULT = os.getenv("RAG_FORCE_FRESH_DEFAULT", "false").lower() == "true"

# Minimum similarity to reuse a cached workflow (0.0–1.0, ChromaDB + embeddings only)
RAG_MIN_SIMILARITY = float(os.getenv("RAG_MIN_SIMILARITY", "0.75"))

# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))

# ---------------------------------------------------------------------------
# API / CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8501",   # Streamlit
    "http://127.0.0.1:8501",
    "http://localhost:5500",   # ✅ ADDED - Python http.server frontend
    "http://127.0.0.1:5500",   # ✅ ADDED
    "http://localhost:5173",   # ✅ ADDED - Vite dev server (if needed)
    "http://127.0.0.1:5173",   # ✅ ADDED
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
MAX_CONCURRENT_TESTS = int(os.getenv("MAX_CONCURRENT_TESTS", "1"))
TEST_CLEANUP_DAYS = int(os.getenv("TEST_CLEANUP_DAYS", "7"))
DEFAULT_NAVIGATE_URL = "https://www.google.com"

VALID_ACTIONS = [
    "navigate", "click", "fill", "press", "wait",
    "assert", "download", "scroll", "hover", "select", "extract",
]

# Screenshot directory alias for streamlit_app.py
SCREENSHOT_DIR = SCREENSHOTS_DIR
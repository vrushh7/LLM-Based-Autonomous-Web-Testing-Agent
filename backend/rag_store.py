"""
RAG Store Module — Enhanced for ALL 8 Requirements
Stores and retrieves successful selectors and workflows using ChromaDB.
Falls back to JSON file storage if ChromaDB is unavailable.

✅ ENHANCED FOR:
- Monitoring workflows (stock, crypto, product price monitoring)
- Flight comparison patterns
- YouTube interaction patterns
- Google Images download patterns
- Smart login patterns
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GLOBAL EXTRACTOR - SINGLE SOURCE OF TRUTH
# ---------------------------------------------------------------------------

def extract_search_term(text: str) -> Optional[str]:
    """Extract search term from instruction text."""
    if not text:
        return None

    text = text.strip()
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

    # PRIORITY 1: Quoted text
    quoted_matches = re.findall(r'["\']([^"\']{2,100})["\']', text)
    if quoted_matches:
        term = max(quoted_matches, key=len).strip()
        if 1 < len(term) < 100:
            logger.info(f"[Extractor] Quoted term: '{term}'")
            return term

    # PRIORITY 2: "search for X"
    pattern = r'search\s+for\s+(.+?)(?:\s+(?:and|then|on\s+google|on\s+amazon|click|press|download|image|photo)\b|$)'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        term = m.group(1).strip().rstrip('.,;!?')
        if 1 < len(term) < 100:
            logger.info(f"[Extractor] 'search for' pattern: '{term}'")
            return term

    # PRIORITY 3: "search X"
    pattern = r'search\s+(.+?)(?:\s+(?:and|then|on\s+google|on\s+amazon|click|press|download)\b|$)'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        term = m.group(1).strip().rstrip('.,;!?')
        if 1 < len(term) < 100:
            logger.info(f"[Extractor] 'search' pattern: '{term}'")
            return term

    # PRIORITY 4: "find X"
    pattern = r'find\s+(.+?)(?:\s+(?:and|then|on|in|$))'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        term = m.group(1).strip().rstrip('.,;!?')
        if 1 < len(term) < 100:
            logger.info(f"[Extractor] 'find' pattern: '{term}'")
            return term

    # PRIORITY 5: "look up X"
    pattern = r'look\s+up\s+(.+?)(?:\s+(?:and|then|on|in|$))'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        term = m.group(1).strip().rstrip('.,;!?')
        if 1 < len(term) < 100:
            logger.info(f"[Extractor] 'look up' pattern: '{term}'")
            return term

    # PRIORITY 6: "monitor X" (for monitoring workflows)
    pattern = r'monitor\s+(.+?)(?:\s+(?:and|then|for|at|with|$))'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        term = m.group(1).strip().rstrip('.,;!?')
        if 1 < len(term) < 100:
            logger.info(f"[Extractor] 'monitor' pattern: '{term}'")
            return term

    # PRIORITY 7: "buy if X drops" pattern
    pattern = r'(?:buy|sell|notify)\s+if\s+(.+?)\s+(?:drops|rises|below|above)'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        term = m.group(1).strip().rstrip('.,;!?')
        if 1 < len(term) < 100:
            logger.info(f"[Extractor] 'buy if' pattern: '{term}'")
            return term

    # PRIORITY 8: Fallback
    cleaned = re.sub(r'^(search for|search|find|look up|show me|get|monitor)\s+', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+(?:on\s+google|on\s+amazon|google|amazon)$', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().rstrip('.,;!?')
    
    if 1 < len(cleaned) < 100:
        logger.info(f"[Extractor] Fallback term: '{cleaned}'")
        return cleaned
    
    logger.warning(f"[Extractor] Could not extract term from: '{text[:50]}'")
    return None


def extract_monitor_condition(text: str) -> Optional[Dict]:
    """Extract monitoring condition from instruction text."""
    if not text:
        return None
    
    text = text.lower()
    
    # Pattern: "buy if Tesla drops 5%" or "notify if PS5 price below 45000"
    patterns = [
        (r'(?:buy|sell|notify)\s+if\s+(\w+)\s+drops\s+(\d+(?:\.\d+)?)\%', 'drop_percent'),
        (r'(?:buy|sell|notify)\s+if\s+(\w+)\s+rises\s+(\d+(?:\.\d+)?)\%', 'rise_percent'),
        (r'(?:buy|sell|notify)\s+if\s+(\w+)\s+price\s+below\s+(\d+(?:\.\d+)?)', 'below'),
        (r'(?:buy|sell|notify)\s+if\s+(\w+)\s+price\s+above\s+(\d+(?:\.\d+)?)', 'above'),
        (r'(?:buy|sell|notify)\s+if\s+(\w+)\s+below\s+(\d+(?:\.\d+)?)', 'below'),
        (r'(?:buy|sell|notify)\s+if\s+(\w+)\s+above\s+(\d+(?:\.\d+)?)', 'above'),
    ]
    
    for pattern, cond_type in patterns:
        m = re.search(pattern, text)
        if m:
            return {
                'item': m.group(1),
                'threshold': float(m.group(2)),
                'condition': cond_type
            }
    
    return None


# ---------------------------------------------------------------------------
# Optional ChromaDB import
# ---------------------------------------------------------------------------
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("[RAGStore] ChromaDB not installed. Falling back to JSON storage.")

# Optional sentence-transformers for semantic search
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("[RAGStore] sentence-transformers not installed. Using keyword search fallback.")


# ---------------------------------------------------------------------------
# Domain extraction helpers (module-level so both stores share them)
# ---------------------------------------------------------------------------

# Hard-coded well-known domains for fast lookup
_KNOWN_DOMAINS: Dict[str, str] = {
    "amazon": "amazon",
    "google": "google",
    "facebook": "facebook",
    "twitter": "twitter",
    "github": "github",
    "stackoverflow": "stackoverflow",
    "reddit": "reddit",
    "youtube": "youtube",
    "linkedin": "linkedin",
    "netflix": "netflix",
    "wikipedia": "wikipedia",
    "ebay": "ebay",
    "walmart": "walmart",
    "target": "target",
    "bestbuy": "bestbuy",
    "bing": "bing",
    "yahoo": "yahoo",
    "instagram": "instagram",
    "tiktok": "tiktok",
    "shopify": "shopify",
    "etsy": "etsy",
    "aliexpress": "aliexpress",
    "flipkart": "flipkart",
    "makemytrip": "makemytrip",
    "goibibo": "goibibo",
    "cleartrip": "cleartrip",
}


def extract_domain_from_text(text: str) -> str:
    """
    Extract a canonical domain key from free text or a URL.
    """
    if not text:
        return ""

    text_lower = text.lower()

    # 1. URL hostname extraction
    url_match = re.search(
        r"(?:https?://)?(?:www\.)?([a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)\.[a-z]{2,}",
        text_lower,
    )
    if url_match:
        hostname_root = url_match.group(1)
        if hostname_root in _KNOWN_DOMAINS:
            return _KNOWN_DOMAINS[hostname_root]
        return hostname_root

    # 2. Keyword scan
    for keyword, key in _KNOWN_DOMAINS.items():
        if keyword in text_lower:
            return key

    # 3. Generic "word.tld" pattern
    generic_match = re.search(r"\b([a-z0-9\-]+)\.(com|org|net|io|co|in|uk)\b", text_lower)
    if generic_match:
        return generic_match.group(1)

    return ""


# ---------------------------------------------------------------------------
# JSON Fallback Store (preserved, no changes needed)
# ---------------------------------------------------------------------------

class JSONFallbackStore:
    """Simple JSON-based store when ChromaDB is unavailable."""

    def __init__(self, path: Path):
        self.path = path
        self._data: Dict[str, List[Dict]] = {"selectors": [], "workflows": []}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning(f"[JSONFallbackStore] Could not load store: {e}")

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[JSONFallbackStore] Could not save store: {e}")

    def add_selector(self, description: str, selector: str, url_pattern: str, success_count: int = 1):
        entry = {
            "description": description,
            "selector": selector,
            "url_pattern": url_pattern,
            "success_count": success_count,
            "last_used": datetime.now().isoformat(),
        }
        for item in self._data["selectors"]:
            if item["selector"] == selector and item["url_pattern"] == url_pattern:
                item["success_count"] += 1
                item["last_used"] = entry["last_used"]
                self._save()
                return
        self._data["selectors"].append(entry)
        self._save()

    def search_selectors(self, query: str, url_pattern: str = "", top_k: int = 3) -> List[Dict]:
        results = []
        query_words = set(query.lower().split())
        for item in self._data["selectors"]:
            desc_words = set(item["description"].lower().split())
            overlap = len(query_words & desc_words)
            url_match = 1 if url_pattern and url_pattern in item.get("url_pattern", "") else 0
            score = overlap + url_match * 2 + item.get("success_count", 1) * 0.1
            if overlap > 0 or url_match > 0:
                results.append({**item, "_score": score})
        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]

    def add_workflow(self, instruction: str, steps: List[Dict], success: bool):
        domain = extract_domain_from_text(instruction)
        entry = {
            "instruction": instruction,
            "steps": steps,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "use_count": 1,
            "domain": domain,
        }
        self._data["workflows"].append(entry)
        if len(self._data["workflows"]) > 200:
            self._data["workflows"] = self._data["workflows"][-200:]
        self._save()

    def search_workflows(self, query: str, top_k: int = 3) -> List[Dict]:
        results = []
        query_words = set(query.lower().split())
        query_domain = extract_domain_from_text(query)

        for item in self._data["workflows"]:
            if not item.get("success"):
                continue

            item_domain = item.get("domain", "")

            if query_domain:
                if item_domain != query_domain:
                    logger.debug(f"[JSONFallbackStore] Skipping workflow — domain mismatch")
                    continue

            instr_words = set(item["instruction"].lower().split())
            overlap = len(query_words & instr_words)
            score = overlap + (10 if query_domain and item_domain == query_domain else 0)

            if overlap > 0 or (query_domain and item_domain == query_domain):
                results.append({**item, "_score": score})

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]

    def get_stats(self) -> Dict:
        successful = [w for w in self._data["workflows"] if w.get("success")]
        domains: Dict[str, int] = {}
        for w in successful:
            d = w.get("domain", "unknown") or "unknown"
            domains[d] = domains.get(d, 0) + 1
        return {
            "total_selectors": len(self._data["selectors"]),
            "total_workflows": len(self._data["workflows"]),
            "successful_workflows": len(successful),
            "domains": domains,
        }

    def clear(self):
        self._data = {"selectors": [], "workflows": []}
        self._save()
        logger.info("[JSONFallbackStore] Store cleared.")


# ---------------------------------------------------------------------------
# ChromaDB Store (preserved, no changes needed)
# ---------------------------------------------------------------------------

class ChromaDBStore:
    """ChromaDB-backed RAG store with optional semantic embeddings."""

    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self.selector_collection = self.client.get_or_create_collection(
            name="selectors",
            metadata={"hnsw:space": "cosine"},
        )
        self.workflow_collection = self.client.get_or_create_collection(
            name="workflows",
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = None
        if EMBEDDINGS_AVAILABLE:
            try:
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("[ChromaDBStore] Semantic embeddings enabled.")
            except Exception as e:
                logger.warning(f"[ChromaDBStore] Could not load embedder: {e}")

    def _embed(self, text: str) -> Optional[List[float]]:
        if self._embedder:
            try:
                return self._embedder.encode(text).tolist()
            except Exception:
                pass
        return None

    def add_selector(self, description: str, selector: str, url_pattern: str, success_count: int = 1):
        doc_id = f"sel_{hash(selector + url_pattern) & 0xFFFFFF}"
        try:
            existing = self.selector_collection.get(ids=[doc_id])
            if existing["ids"]:
                meta = existing["metadatas"][0]
                meta["success_count"] = meta.get("success_count", 1) + 1
                meta["last_used"] = datetime.now().isoformat()
                self.selector_collection.update(ids=[doc_id], metadatas=[meta])
                return
        except Exception:
            pass

        embedding = self._embed(description)
        kwargs: Dict = dict(
            ids=[doc_id],
            documents=[description],
            metadatas=[{
                "selector": selector,
                "url_pattern": url_pattern,
                "success_count": success_count,
                "last_used": datetime.now().isoformat(),
            }],
        )
        if embedding:
            kwargs["embeddings"] = [embedding]
        self.selector_collection.add(**kwargs)

    def search_selectors(self, query: str, url_pattern: str = "", top_k: int = 3) -> List[Dict]:
        try:
            count = self.selector_collection.count()
            if count == 0:
                return []
            embedding = self._embed(query)
            kwargs: Dict = dict(n_results=min(top_k, count))
            if embedding:
                kwargs["query_embeddings"] = [embedding]
            else:
                kwargs["query_texts"] = [query]
            results = self.selector_collection.query(**kwargs)
            out = []
            for i, _doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                out.append({
                    "description": results["documents"][0][i],
                    "selector": meta.get("selector", ""),
                    "url_pattern": meta.get("url_pattern", ""),
                    "success_count": meta.get("success_count", 1),
                })
            return out
        except Exception as e:
            logger.warning(f"[ChromaDBStore] selector search error: {e}")
            return []

    def add_workflow(self, instruction: str, steps: List[Dict], success: bool):
        doc_id = f"wf_{int(time.time() * 1000) & 0xFFFFFFF}"
        domain = extract_domain_from_text(instruction)
        embedding = self._embed(instruction)
        kwargs: Dict = dict(
            ids=[doc_id],
            documents=[instruction],
            metadatas=[{
                "steps_json": json.dumps(steps),
                "success": str(success),
                "timestamp": datetime.now().isoformat(),
                "domain": domain,
            }],
        )
        if embedding:
            kwargs["embeddings"] = [embedding]
        try:
            self.workflow_collection.add(**kwargs)
        except Exception as e:
            logger.warning(f"[ChromaDBStore] add_workflow error: {e}")

    def search_workflows(self, query: str, top_k: int = 3) -> List[Dict]:
        try:
            count = self.workflow_collection.count()
            if count == 0:
                return []

            query_domain = extract_domain_from_text(query)
            embedding = self._embed(query)
            fetch_n = min(top_k * 3, count)
            kwargs: Dict = dict(n_results=fetch_n)
            if embedding:
                kwargs["query_embeddings"] = [embedding]
            else:
                kwargs["query_texts"] = [query]
            results = self.workflow_collection.query(**kwargs)

            out = []
            for i, _doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]

                if meta.get("success") != "True":
                    continue

                stored_domain = meta.get("domain", "") or ""

                if query_domain:
                    if stored_domain and stored_domain != query_domain:
                        logger.debug(f"[ChromaDBStore] Skipping workflow — domain mismatch")
                        continue

                try:
                    steps = json.loads(meta.get("steps_json", "[]"))
                except Exception:
                    steps = []

                out.append({
                    "instruction": results["documents"][0][i],
                    "steps": steps,
                    "timestamp": meta.get("timestamp", ""),
                    "domain": stored_domain,
                })

                if len(out) >= top_k:
                    break

            return out
        except Exception as e:
            logger.warning(f"[ChromaDBStore] workflow search error: {e}")
            return []

    def get_stats(self) -> Dict:
        return {
            "total_selectors": self.selector_collection.count(),
            "total_workflows": self.workflow_collection.count(),
            "embeddings_enabled": self._embedder is not None,
        }

    def clear(self):
        try:
            self.client.delete_collection("selectors")
            self.client.delete_collection("workflows")
            self.selector_collection = self.client.get_or_create_collection(
                name="selectors", metadata={"hnsw:space": "cosine"}
            )
            self.workflow_collection = self.client.get_or_create_collection(
                name="workflows", metadata={"hnsw:space": "cosine"}
            )
            logger.info("[ChromaDBStore] Store cleared.")
        except Exception as e:
            logger.error(f"[ChromaDBStore] clear error: {e}")


# ---------------------------------------------------------------------------
# RAG Store (unified interface) - ENHANCED
# ---------------------------------------------------------------------------

class RAGStore:
    """
    Unified RAG store interface.
    Uses ChromaDB when available, falls back to JSON.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        base_dir.mkdir(parents=True, exist_ok=True)

        if CHROMADB_AVAILABLE:
            try:
                self._store = ChromaDBStore(base_dir / "chromadb")
                self._backend = "chromadb"
                logger.info("[RAGStore] Using ChromaDB backend.")
            except Exception as e:
                logger.warning(f"[RAGStore] ChromaDB init failed ({e}), using JSON fallback.")
                self._store = JSONFallbackStore(base_dir / "rag_store.json")
                self._backend = "json"
        else:
            self._store = JSONFallbackStore(base_dir / "rag_store.json")
            self._backend = "json"

        self._seed_known_selectors()

    def _seed_known_selectors(self):
        """Pre-populate with reliable selectors for common sites."""
        known = [
            # Google
            ("Google search box", "textarea[name='q']", "google.com"),
            ("Google search input", "input[name='q']", "google.com"),
            ("Google Images tab", "a[href*='tbm=isch']", "google.com"),
            ("Google search button", "input[value='Google Search']", "google.com"),
            # Amazon
            ("Amazon search box", "input[id='twotabsearchtextbox']", "amazon.in"),
            ("Amazon search button", "input[id='nav-search-submit-button']", "amazon.in"),
            ("Amazon add to cart", "#add-to-cart-button", "amazon.in"),
            ("Amazon buy now", "#buy-now-button", "amazon.in"),
            ("Amazon product result", "div[data-component-type='s-search-result'] h2 a", "amazon.in"),
            ("Amazon variant dropdown", "select[name='dropdown_selected_size_name']", "amazon.in"),
            # Flipkart
            ("Flipkart search box", "input._2P_LnL", "flipkart.com"),
            ("Flipkart search button", "button._2i2sHZ", "flipkart.com"),
            ("Flipkart add to cart", "button._2KpZ6l", "flipkart.com"),
            ("Flipkart product result", "div._1AtVbE a._1fQZEK", "flipkart.com"),
            # YouTube
            ("YouTube search box", "input#search", "youtube.com"),
            ("YouTube search button", "button#search-icon-legacy", "youtube.com"),
            ("YouTube video thumbnail", "#dismissible ytd-video-renderer a#thumbnail", "youtube.com"),
            ("YouTube like button", "button.yt-spec-button-shape-next--like", "youtube.com"),
            ("YouTube fullscreen", "button.ytp-fullscreen-button", "youtube.com"),
            # Login
            ("Login email field", "input[type='email']", "*"),
            ("Login password field", "input[type='password']", "*"),
            ("Login submit button", "button[type='submit']", "*"),
            # Generic
            ("Generic submit button", "button[type='submit']", "*"),
            ("Generic search input", "input[type='search']", "*"),
            ("Generic text input", "input[type='text']", "*"),
        ]
        for desc, selector, pattern in known:
            try:
                self._store.add_selector(desc, selector, pattern, success_count=5)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_success(self, description: str, selector: str, url: str):
        """Record a successful selector usage."""
        pattern = _extract_domain_from_url(url)
        try:
            self._store.add_selector(description, selector, pattern)
            logger.debug(f"[RAGStore] Recorded success: '{selector}' for '{description}'")
        except Exception as e:
            logger.warning(f"[RAGStore] record_success error: {e}")

    def record_workflow(self, instruction: str, steps: List[Dict], success: bool):
        """Record an entire workflow result."""
        try:
            self._store.add_workflow(instruction, steps, success)
            logger.debug(f"[RAGStore] Recorded workflow (success={success}): '{instruction[:60]}'")
        except Exception as e:
            logger.warning(f"[RAGStore] record_workflow error: {e}")

    def find_similar_selectors(self, description: str, url: str = "", top_k: int = 3) -> List[str]:
        """Return a ranked list of CSS selectors that worked for similar steps."""
        pattern = _extract_domain_from_url(url)
        try:
            results = self._store.search_selectors(description, pattern, top_k)
            return [r["selector"] for r in results if r.get("selector")]
        except Exception as e:
            logger.warning(f"[RAGStore] find_similar_selectors error: {e}")
            return []

    def find_similar_workflow(
        self,
        instruction: str,
        force_fresh: bool = False,
    ) -> Optional[List[Dict]]:
        """
        Return steps from the most similar successful past workflow.
        """
        if force_fresh:
            logger.info("[RAGStore] force_fresh=True — skipping RAG workflow lookup.")
            return None

        query_domain = extract_domain_from_text(instruction)

        try:
            results = self._store.search_workflows(instruction, top_k=1)
            if results:
                logger.info(f"[RAGStore] Reusing workflow for: '{instruction[:60]}'")
                return results[0]["steps"]
            else:
                logger.info(f"[RAGStore] No matching workflow for domain='{query_domain}'")
        except Exception as e:
            logger.warning(f"[RAGStore] find_similar_workflow error: {e}")

        return None

    def find_similar_workflow_parameterized(
        self,
        instruction: str,
        force_fresh: bool = False,
    ) -> Tuple[Optional[List[Dict]], Dict]:
        """
        Find a similar workflow and parameterize it with the new search term.
        """
        if force_fresh:
            logger.info("[RAGStore] force_fresh=True — skipping RAG workflow lookup.")
            return None, {}
        
        query_domain = extract_domain_from_text(instruction)
        
        try:
            results = self._store.search_workflows(instruction, top_k=1)
            if not results:
                logger.info(f"[RAGStore] No matching workflow for domain='{query_domain}'")
                return None, {}
            
            workflow = results[0]
            stored_instruction = workflow.get("instruction", "")
            stored_steps = workflow["steps"]
            
            new_search_term = extract_search_term(instruction)
            old_search_term = extract_search_term(stored_instruction)
            
            logger.info(f"[RAGStore] Found workflow: '{stored_instruction[:60]}'")
            logger.info(f"[RAGStore] Extracted terms - old: '{old_search_term}', new: '{new_search_term}'")
            
            if new_search_term and old_search_term and new_search_term != old_search_term:
                parameterized_steps = []
                modifications_made = 0
                
                for step in stored_steps:
                    step_copy = step.copy()
                    
                    if step_copy.get("value") and old_search_term in step_copy["value"]:
                        step_copy["value"] = step_copy["value"].replace(old_search_term, new_search_term)
                        modifications_made += 1
                    
                    if step_copy.get("description") and old_search_term in step_copy["description"]:
                        step_copy["description"] = step_copy["description"].replace(
                            old_search_term, new_search_term
                        )
                        modifications_made += 1
                    
                    parameterized_steps.append(step_copy)
                
                if modifications_made > 0:
                    logger.info(f"[RAGStore] ✓ Parameterized workflow: '{old_search_term}' → '{new_search_term}'")
                    return parameterized_steps, {
                        "old_term": old_search_term,
                        "new_term": new_search_term,
                        "parameterized": True
                    }
                else:
                    return stored_steps, {"original": True, "parameterized": False}
            
            return stored_steps, {"original": True, "parameterized": False}
            
        except Exception as e:
            logger.warning(f"[RAGStore] find_similar_workflow_parameterized error: {e}")
            return None, {}

    def get_context_for_prompt(
        self,
        instruction: str,
        url: str = "",
        force_fresh: bool = False,
    ) -> str:
        """Return a prompt-ready context string with relevant past selectors/workflows."""
        lines = []

        if not force_fresh:
            workflow, metadata = self.find_similar_workflow_parameterized(instruction, force_fresh=False)
            if workflow:
                lines.append("=== Similar past workflow that SUCCEEDED ===")
                for s in workflow[:8]:
                    lines.append(f"  {s.get('action', '?')}: {s.get('description', '')}")
                if metadata.get("parameterized"):
                    lines.append(f"  [Note: Search term parameterized from '{metadata.get('old_term')}']")
                lines.append("")

        selectors = self.find_similar_selectors(instruction, url, top_k=5)
        if selectors:
            lines.append("=== Previously successful selectors ===")
            for sel in selectors:
                lines.append(f"  {sel}")
            lines.append("")

        return "\n".join(lines) if lines else ""

    def clear(self):
        """Wipe all stored RAG data."""
        try:
            self._store.clear()
            logger.info("[RAGStore] All data cleared.")
        except Exception as e:
            logger.error(f"[RAGStore] clear error: {e}")

    def get_stats(self) -> Dict:
        try:
            stats = self._store.get_stats()
            stats["backend"] = self._backend
            return stats
        except Exception:
            return {"backend": self._backend, "error": "stats unavailable"}


# ---------------------------------------------------------------------------
# URL-only domain helper
# ---------------------------------------------------------------------------

def _extract_domain_from_url(url: str) -> str:
    match = re.search(r"(?:https?://)?(?:www\.)?([^/\s]+)", url or "")
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_rag_store_instance: Optional[RAGStore] = None


def get_rag_store() -> RAGStore:
    global _rag_store_instance
    if _rag_store_instance is None:
        base = Path(__file__).parent / "rag_data"
        _rag_store_instance = RAGStore(base)
    return _rag_store_instance
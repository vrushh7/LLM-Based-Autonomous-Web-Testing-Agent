"""
LLM Service Module — Production Upgrade
RAG-enhanced prompt engineering, retry logic, fallback plan generation.

CRITICAL FIX: URL detection happens FIRST - bypasses ALL LLM/RAG logic
"""

import logging
import re
import requests
from typing import Dict, List, Optional, Tuple

import config
from debug_agent import debug_agent
from rag_store import get_rag_store, extract_domain_from_text, extract_search_term
from step_schema import validate_and_repair_plan

logger = logging.getLogger(__name__)


class LLMService:

    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL
        self.model = config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS
        self._rag = get_rag_store()

    # ------------------------------------------------------------------
    # URL detection and extraction
    # ------------------------------------------------------------------

    def _extract_url_from_instruction(self, instruction: str) -> Optional[str]:
        """Extract any valid URL from the instruction."""
        url_pattern = r'https?://[^\s]+'
        matches = re.findall(url_pattern, instruction, re.IGNORECASE)
        
        if matches:
            url = matches[0].strip()
            url = re.sub(r'[.,;!?)]$', '', url)
            logger.info(f"[LLMService] 🔥 Detected URL in instruction: {url}")
            return url
        
        return None

    def _extract_credentials(self, instruction: str) -> tuple:
        """Strong credential extraction with multiple patterns."""
        # Username extraction patterns
        username_match = re.search(
            r'(?:username|user|email)\s*[:=]\s*["\']?([a-zA-Z0-9@._-]+)', 
            instruction, 
            re.IGNORECASE
        )
        
        if not username_match:
            username_match = re.search(
                r'(?:username|user|email)\s+([a-zA-Z0-9@._-]+)', 
                instruction, 
                re.IGNORECASE
            )
        
        if not username_match:
            words = instruction.split()
            for i, word in enumerate(words):
                if word.lower() in ['username', 'user', 'email'] and i + 1 < len(words):
                    username_match = re.search(r'([a-zA-Z0-9@._-]+)', words[i + 1])
                    break
        
        # Password extraction patterns
        password_match = re.search(
            r'(?:password|pass|pwd)\s*[:=]\s*["\']?([a-zA-Z0-9@._-]+)', 
            instruction, 
            re.IGNORECASE
        )
        
        if not password_match:
            password_match = re.search(
                r'(?:password|pass|pwd)\s+([a-zA-Z0-9@._-]+)', 
                instruction, 
                re.IGNORECASE
            )
        
        if not password_match:
            words = instruction.split()
            for i, word in enumerate(words):
                if word.lower() in ['password', 'pass', 'pwd'] and i + 1 < len(words):
                    password_match = re.search(r'([a-zA-Z0-9@._-]+)', words[i + 1])
                    break
        
        username = username_match.group(1) if username_match else None
        password = password_match.group(1) if password_match else None
        
        # Fallback values
        if not username or len(username) < 2:
            username = "sdmites"
            logger.warning(f"[LLMService] Using fallback username: {username}")
        
        if not password or len(password) < 2:
            password = "good"
            logger.warning(f"[LLMService] Using fallback password: {password}")
        
        print(f"\n[CREDENTIAL EXTRACTION]")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print(f"  From instruction: {instruction[:100]}...\n")
        
        return username, password

    def _is_amazon_url(self, url: str) -> bool:
        """Check if URL is Amazon"""
        return "amazon" in url.lower()

    def _extract_search_term_amazon(self, instruction: str) -> str:
        """Extract search term for Amazon"""
        # Try quoted terms first
        quoted = re.search(r'"([^"]+)"', instruction)
        if quoted:
            return quoted.group(1)
        
        # Try after "for" or "search for"
        after_for = re.search(r'(?:search for|for)\s+["\']?([a-zA-Z0-9\s]+?)(?:["\']|$)', instruction, re.IGNORECASE)
        if after_for:
            return after_for.group(1).strip()
        
        # Use the global extractor
        return extract_search_term(instruction) or "wireless headphones"

    # ------------------------------------------------------------------
    # 🔥🔥🔥 DIRECT URL HANDLER - Called FIRST, BEFORE anything else
    # ------------------------------------------------------------------

    def _create_direct_url_plan(self, instruction: str, url: str) -> Dict:
        """
        Create a test plan directly from URL without calling LLM or RAG.
        This is called IMMEDIATELY when a URL is detected.
        """
        logger.warning(f"[LLMService] 🔥🔥🔥 BYPASSING LLM & RAG — direct URL plan for: {url}")
        
        instr_lower = instruction.lower()
        
        # 🔥 NEW: Check for Amazon
        if self._is_amazon_url(url):
            logger.info("[LLMService] Detected Amazon - creating complete shopping workflow")
            search_term = self._extract_search_term_amazon(instruction)
            
            steps = [
                {"action": "navigate", "url": url, "description": f"Navigate to {url}"},
                {"action": "wait", "duration": 3000, "description": "Wait for page to load"},
                {"action": "fill", "selector": "input[id='twotabsearchtextbox']", "value": search_term, "description": f"Search for: {search_term}"},
                {"action": "press", "key": "Enter", "description": "Submit search"},
                {"action": "wait", "duration": 5000, "description": "Wait for search results"},
                {"action": "click", "selector": "div[data-component-type='s-search-result'] h2 a, div.s-result-item h2 a, div[data-component-type='s-search-result']:first-child h2 a", "description": "Click first product"},
                {"action": "wait", "duration": 4000, "description": "Wait for product page"},
                {"action": "click", "selector": "input#add-to-cart-button, #add-to-cart-button, input[name='submit.add-to-cart']", "description": "Add to Cart"},
                {"action": "wait", "duration": 3000, "description": "Wait for cart update"},
                {"action": "assert", "assertion_type": "visible", "selector": "#nav-cart-count", "description": "Verify cart exists"}
            ]
            
            plan = {"steps": steps, "_source": "direct_url_bypass_amazon", "_bypassed_llm": True, "_bypassed_rag": True}
            
            # Print debug output
            print("\n" + "="*70)
            print("🔥🔥🔥 AMAZON DIRECT URL PLAN (LLM & RAG BYPASSED)")
            print("="*70)
            for i, step in enumerate(steps, 1):
                action = step.get("action")
                desc = step.get("description", "")
                print(f"Step {i}: {action} - {desc[:60]}")
            print("="*70 + "\n")
            
            return plan
        
        # Start with navigation and wait for non-Amazon URLs
        steps = [
            {"action": "navigate", "url": url, "description": f"Navigate directly to {url}"},
            {"action": "wait", "duration": 3000, "description": "Wait for page to load"}
        ]
        
        # Check for login form
        is_login = any(keyword in instr_lower for keyword in ["login", "sign in", "log in", "signin"])
        has_username = any(keyword in instr_lower for keyword in ["username", "user name", "email", "userid"])
        has_password = any(keyword in instr_lower for keyword in ["password", "pass", "pwd"])
        
        if is_login or has_username or has_password:
            logger.info("[LLMService] Detected login form - adding credentials with proper assertions")
            
            username, password = self._extract_credentials(instruction)
            
            steps.extend([
                {"action": "fill", "selector": "input[type='text'], input[name='username'], input[id='username'], input[name='email'], input[id='email'], input[name='user'], input[id='user']", "value": username, "description": f"Enter username: {username}"},
                {"action": "wait", "duration": 500, "description": "Small pause after username"},
                {"action": "fill", "selector": "input[type='password'], input[name='password'], input[id='password'], input[name='pass'], input[id='pass']", "value": password, "description": "Enter password"},
                {"action": "wait", "duration": 500, "description": "Small pause after password"},
                {"action": "press", "key": "Enter", "description": "Submit login using Enter key"},
                {"action": "wait", "duration": 3000, "description": "Wait for form submission"},
                {"action": "click", "selector": "button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign'), input[value='Login'], button:has-text('Submit'), form button", "description": "Click Login button (fallback)"},
                {"action": "wait", "duration": 3000, "description": "Wait for login to complete"},
                {"action": "assert", "assertion_type": "count_eq", "selector": "input[type='password']", "expected": "0", "description": "Verify password field is gone"},
                {"action": "assert", "assertion_type": "visible", "selector": "body", "description": "Verify page body is visible"}
            ])
        
        # Check for search form (if no login detected)
        elif any(keyword in instr_lower for keyword in ["search", "find", "look for"]):
            search_term = extract_search_term(instruction)
            if not search_term:
                words = [w for w in instruction.split() if len(w) > 2][-1] if instruction.split() else "search"
                search_term = words
            
            steps.extend([
                {"action": "fill", "selector": "input[type='search'], input[name='search'], input[name='q'], input[type='text']", "value": search_term, "description": f"Search for: {search_term}"},
                {"action": "press", "key": "Enter", "description": "Submit search"},
                {"action": "wait", "duration": 3000, "description": "Wait for results"},
                {"action": "assert", "assertion_type": "visible", "selector": "body", "description": "Verify results page loaded"}
            ])
        
        plan = {
            "steps": steps,
            "_source": "direct_url_bypass",
            "_bypassed_llm": True,
            "_bypassed_rag": True
        }
        
        # Print debug output
        print("\n" + "="*70)
        print("🔥🔥🔥 DIRECT URL PLAN (LLM & RAG BYPASSED)")
        print("="*70)
        for i, step in enumerate(steps, 1):
            action = step.get("action")
            desc = step.get("description", "")
            print(f"Step {i}: {action} - {desc[:60]}")
        print("="*70 + "\n")
        
        return plan

    # ------------------------------------------------------------------
    # Regular LLM flow (only used when NO URL detected)
    # ------------------------------------------------------------------

    def _needs_fresh_plan(self, instruction: str) -> bool:
        """Detect if instruction has additional actions that require a fresh plan."""
        instruction_lower = instruction.lower()
        
        extra_action_keywords = [
            "click", "download", "add to cart", "images", "pictures", 
            "photos", "buy", "purchase", "save", "open", "select", 
            "choose", "filter", "sort", "review", "view", "expand",
            "images tab", "image tab", "photo tab", "login", "sign in",
            "username", "password", "submit", "form", "fill"
        ]
        
        for keyword in extra_action_keywords:
            if ' ' in keyword:
                if keyword in instruction_lower:
                    return True
            else:
                if re.search(rf"\b{keyword}\b", instruction_lower):
                    return True
        return False

    def _rag_steps_sufficient(self, steps: List[Dict], instruction: str) -> bool:
        """Check if steps from RAG include all required actions."""
        instruction_lower = instruction.lower()
        
        if "add to cart" in instruction_lower:
            has_cart = any(
                step.get("action") == "click" and 
                "cart" in step.get("description", "").lower()
                for step in steps
            )
            if not has_cart:
                return False
        
        if "download" in instruction_lower:
            has_download = any(step.get("action") == "download" for step in steps)
            if not has_download:
                return False
        
        return True

    def _force_search_term_override(self, test_plan: Dict, instruction: str) -> Dict:
        """Force override LLM's search term with extracted one."""
        if not test_plan or not test_plan.get("steps"):
            return test_plan
        
        extracted_term = extract_search_term(instruction)
        if not extracted_term:
            return test_plan
        
        plan_copy = test_plan.copy()
        
        for step in plan_copy.get("steps", []):
            if step.get("action") == "fill":
                old_value = step.get("value", "")
                selector = step.get("selector", "").lower()
                description = step.get("description", "").lower()
                
                is_search_box = any(keyword in selector or keyword in description 
                                   for keyword in ['search', 'q', 'twotabsearchtextbox', 'query'])
                
                if is_search_box and old_value != extracted_term:
                    step["value"] = extracted_term
                    logger.info(f"[LLMService] Override: '{old_value}' → '{extracted_term}'")
        
        return plan_copy

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def generate_test_steps(
        self,
        user_instruction: str,
        force_fresh: bool = False,
    ) -> Dict:
        """Generate a test plan for the given instruction."""
        
        # STEP 1: CHECK FOR URL - HIGHEST PRIORITY
        detected_url = self._extract_url_from_instruction(user_instruction)
        
        if detected_url:
            logger.warning(f"[LLMService] 🔥🔥🔥 URL DETECTED - BYPASSING ALL LLM/RAG LOGIC")
            logger.info(f"[LLMService] URL: {detected_url}")
            
            plan = self._create_direct_url_plan(user_instruction, detected_url)
            plan, issues = validate_and_repair_plan(plan, user_instruction)
            
            return {
                "success": True,
                "test_plan": plan,
                "error": None,
                "was_repaired": True,
                "validation_issues": issues,
                "bypassed_llm": True,
                "bypassed_rag": True
            }
        
        # STEP 2: NO URL DETECTED - Use normal LLM + RAG flow
        logger.info("[LLMService] No URL detected - using standard LLM flow")
        
        query_domain = extract_domain_from_text(user_instruction)
        auto_force_fresh = self._needs_fresh_plan(user_instruction)
        effective_force_fresh = force_fresh or auto_force_fresh
        
        logger.info(f"[LLMService] Generating plan | domain='{query_domain}' | force_fresh={effective_force_fresh}")

        # 1. Check RAG for parameterized workflow
        if not effective_force_fresh:
            rag_steps, metadata = self._rag.find_similar_workflow_parameterized(
                user_instruction, force_fresh=False
            )
            
            if rag_steps and self._rag_steps_sufficient(rag_steps, user_instruction):
                logger.info(f"[LLMService] ✅ Reusing workflow from RAG")
                test_plan = {"url": None, "steps": rag_steps, "_source": "rag_parameterized"}
                test_plan = self._force_search_term_override(test_plan, user_instruction)
                test_plan, issues = validate_and_repair_plan(test_plan, user_instruction)
                return {
                    "success": True,
                    "test_plan": test_plan,
                    "error": None,
                    "was_repaired": bool(issues),
                    "validation_issues": issues,
                    "parameterization": metadata,
                }

        # 2. Build prompt for LLM
        rag_context = self._rag.get_context_for_prompt(user_instruction, force_fresh=effective_force_fresh)
        prompt = self._build_prompt(user_instruction, rag_context)

        # 3. First LLM call
        try:
            raw = self._call_ollama(prompt)
            logger.debug(f"[LLMService] Raw response:\n{raw[:500]}")
        except Exception as e:
            logger.error(f"[LLMService] Ollama call failed: {e}")
            return self._fallback_result(user_instruction, str(e))

        test_plan, was_repaired = debug_agent.fix_test_plan(raw, instruction=user_instruction)
        
        if test_plan:
            logger.info(f"[LLMService] Plan parsed, steps={len(test_plan.get('steps', []))}")
            test_plan = self._force_search_term_override(test_plan, user_instruction)
            test_plan, issues = validate_and_repair_plan(test_plan, user_instruction)
            
            print("\n" + "="*60)
            print("LLM GENERATED PLAN:")
            for i, step in enumerate(test_plan.get("steps", []), 1):
                print(f"Step {i}: {step.get('action')} - {step.get('description', '')[:60]}")
            print("="*60 + "\n")
            
            return {
                "success": True,
                "test_plan": test_plan,
                "error": None,
                "was_repaired": was_repaired or bool(issues),
                "validation_issues": issues,
            }

        # 4. Fallback
        logger.warning("[LLMService] Using fallback plan")
        return self._fallback_result(user_instruction, "LLM parse failed")

    # ------------------------------------------------------------------
    # Selector healing
    # ------------------------------------------------------------------

    def fix_selector_via_llm(self, failed_step: Dict, error_message: str) -> Optional[str]:
        prompt = (
            f"Suggest ONE better CSS selector.\n"
            f"Action: {failed_step.get('action')}\n"
            f"Description: {failed_step.get('description')}\n"
            f"Current: {failed_step.get('selector')}\n"
            f"Error: {error_message}\n"
            f"Selector:"
        )
        try:
            raw = self._call_ollama(prompt, max_tokens=60, temperature=0.0).strip().strip('"\'`')
            if raw and len(raw) < 200:
                logger.info(f"[LLMService] Suggested selector: '{raw}'")
                return raw
        except Exception as e:
            logger.warning(f"[LLMService] Selector call failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Ollama HTTP call
    # ------------------------------------------------------------------

    def _call_ollama(self, prompt: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json().get("response", "")

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(self, instruction: str, rag_context: str = "") -> str:
        rag_section = f"\nRELEVANT PAST EXPERIENCE:\n{rag_context}\n" if rag_context else ""
        
        return f"""Convert instruction to JSON test plan.

Instruction: "{instruction}"
{rag_section}
Output: {{"steps": [{{"action": "navigate|click|fill|press|wait|assert|download", "description": "...", "selector": "...", "value": "...", "url": "...", "key": "...", "duration": 2000, "assertion_type": "visible|text_contains|url_contains|count_eq|count_gt", "expected": "..."}}]}}

Rules:
- Start with navigate
- For Google: selector "textarea[name='q']"
- For Amazon: selector "input[id='twotabsearchtextbox']"
- For login success: use count_eq with selector "input[type='password']" and expected "0"
- Return ONLY valid JSON

JSON:"""

    # ------------------------------------------------------------------
    # Fallback (only used when NO URL detected)
    # ------------------------------------------------------------------

    def _fallback_result(self, instruction: str, error: str) -> Dict:
        plan = self._build_fallback_plan(instruction)
        plan, issues = validate_and_repair_plan(plan, instruction)
        
        print("\n" + "="*60)
        print("FALLBACK PLAN:")
        for i, step in enumerate(plan.get("steps", []), 1):
            print(f"Step {i}: {step.get('action')} - {step.get('description', '')[:60]}")
        print("="*60 + "\n")
        
        return {
            "success": True,
            "test_plan": plan,
            "error": f"LLM failed ({error}); using fallback.",
            "was_repaired": True,
            "validation_issues": issues,
        }

    def _build_fallback_plan(self, instruction: str) -> Dict:
        """Fallback plan - only used when no URL detected."""
        instr_lower = instruction.lower()
        search_term = extract_search_term(instruction)
        
        if not search_term:
            words = [w for w in instruction.split() if len(w) > 2][-3:]
            search_term = " ".join(words) if words else "search"
        
        if "amazon" in instr_lower:
            steps = [
                {"action": "navigate", "url": "https://www.amazon.in", "description": "Open Amazon"},
                {"action": "wait", "duration": 3000},
                {"action": "fill", "selector": "input[id='twotabsearchtextbox']", "value": search_term, "description": f"Search {search_term}"},
                {"action": "press", "key": "Enter"},
                {"action": "wait", "duration": 5000},
            ]
        else:
            steps = [
                {"action": "navigate", "url": "https://www.google.com", "description": "Open Google"},
                {"action": "wait", "duration": 2000},
                {"action": "fill", "selector": "textarea[name='q']", "value": search_term, "description": f"Search {search_term}"},
                {"action": "press", "key": "Enter"},
                {"action": "wait", "duration": 3000},
            ]
        
        return {"steps": steps}


# Singleton
llm_service = LLMService()
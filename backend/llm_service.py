"""
LLM Service Module — Production Upgrade
RAG-enhanced prompt engineering, retry logic, fallback plan generation.

CHANGES:
  - generate_test_steps() accepts force_fresh=True to bypass RAG workflow cache
  - RAG context injection is domain-aware (won't inject Google steps into Amazon tasks)
  - FIXED: Uses GLOBAL extract_search_term() from rag_store (single source of truth)
  - FIXED: FORCE OVERRIDE - LLM output is overridden with extracted search term
  - FIXED: Amazon uses amazon.in instead of .com to avoid login page
  - NEW: Auto-detect when to force fresh plan based on instruction complexity
  - NEW: Check if RAG steps have required actions before reusing
  - IMPROVED: Word boundary detection for keywords
  - IMPROVED: Explicit "images tab" detection
  - IMPROVED: Clear logging when fallback is used due to LLM unavailability
  - FIXED: Robust Amazon selectors for product click and add to cart
"""

import logging
import re
import requests
from typing import Dict, List, Optional

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
    # Helper methods for intelligent RAG reuse
    # ------------------------------------------------------------------

    def _needs_fresh_plan(self, instruction: str) -> bool:
        """
        Detect if instruction has additional actions that require a fresh plan.
        RAG might have a basic workflow, but if user wants extra actions,
        we need to generate a fresh plan with those steps included.
        """
        instruction_lower = instruction.lower()
        
        # Keywords that indicate additional actions beyond basic search
        # Using word boundaries to avoid partial matches (e.g., "clicking" matches "click")
        extra_action_keywords = [
            "click", "download", "add to cart", "images", "pictures", 
            "photos", "buy", "purchase", "save", "open", "select", 
            "choose", "filter", "sort", "review", "view", "expand",
            "images tab", "image tab", "photo tab"
        ]
        
        for keyword in extra_action_keywords:
            # Use word boundary for single words, simple contains for phrases
            if ' ' in keyword:
                # Phrase - simple contains is fine
                if keyword in instruction_lower:
                    logger.info(f"[LLMService] 🔥 Force fresh plan - detected extra action: '{keyword}'")
                    return True
            else:
                # Single word - use word boundary to avoid partial matches
                if re.search(rf"\b{keyword}\b", instruction_lower):
                    logger.info(f"[LLMService] 🔥 Force fresh plan - detected extra action: '{keyword}'")
                    return True
        
        return False

    def _rag_steps_sufficient(self, steps: List[Dict], instruction: str) -> bool:
        """
        Check if the steps from RAG include all required actions from instruction.
        Returns True if RAG workflow is sufficient, False if we need a fresh plan.
        """
        instruction_lower = instruction.lower()
        
        # Check for image-related actions (including "images tab")
        has_image_request = any(
            keyword in instruction_lower 
            for keyword in ["image", "picture", "photo", "images tab", "image tab"]
        )
        
        if has_image_request:
            has_image_action = any(
                step.get("action") == "click" and (
                    "image" in step.get("description", "").lower() or
                    "tbm=isch" in step.get("selector", "") or
                    "img" in step.get("selector", "").lower() or
                    "images tab" in step.get("description", "").lower()
                )
                for step in steps
            )
            if not has_image_action:
                logger.warning(f"[LLMService] ⚠️ RAG steps missing image-related action")
                return False
        
        # Check for add to cart action
        if "add to cart" in instruction_lower or re.search(r"\bbuy\b", instruction_lower) or re.search(r"\bpurchase\b", instruction_lower):
            has_cart_action = any(
                step.get("action") == "click" and (
                    "cart" in step.get("description", "").lower() or
                    "add-to-cart" in step.get("selector", "") or
                    "add to cart" in step.get("description", "").lower()
                )
                for step in steps
            )
            if not has_cart_action:
                logger.warning(f"[LLMService] ⚠️ RAG steps missing add-to-cart action")
                return False
        
        # Check for download action
        if re.search(r"\bdownload\b", instruction_lower) or re.search(r"\bsave\b", instruction_lower):
            has_download = any(step.get("action") == "download" for step in steps)
            if not has_download:
                logger.warning(f"[LLMService] ⚠️ RAG steps missing download action")
                return False
        
        # Check for click action on results
        if re.search(r"\bclick\b", instruction_lower) and "result" in instruction_lower:
            has_click = any(
                step.get("action") == "click" and 
                "result" in step.get("description", "").lower()
                for step in steps
            )
            if not has_click:
                logger.warning(f"[LLMService] ⚠️ RAG steps missing click on result action")
                return False
        
        return True

    def _force_search_term_override(self, test_plan: Dict, instruction: str) -> Dict:
        """
        Force override LLM's search term with extracted one.
        This ensures the correct search term is always used regardless of what LLM generates.
        """
        if not test_plan or not test_plan.get("steps"):
            return test_plan
        
        extracted_term = extract_search_term(instruction)
        if not extracted_term:
            logger.debug(f"[LLMService] No search term extracted, skipping override")
            return test_plan
        
        plan_copy = test_plan.copy()
        overridden = False
        
        for step in plan_copy.get("steps", []):
            if step.get("action") == "fill":
                old_value = step.get("value", "")
                # Check if this is a search box (by selector or description)
                selector = step.get("selector", "").lower()
                description = step.get("description", "").lower()
                
                is_search_box = any(keyword in selector or keyword in description 
                                   for keyword in ['search', 'q', 'twotabsearchtextbox', 'query'])
                
                if is_search_box and old_value != extracted_term:
                    step["value"] = extracted_term
                    overridden = True
                    logger.info(f"[LLMService] 🔥 FORCE OVERRIDE: '{old_value}' → '{extracted_term}'")
        
        if overridden:
            logger.info(f"[LLMService] ✓ LLM search term successfully overridden to: '{extracted_term}'")
        else:
            logger.debug(f"[LLMService] No fill step found to override")
        
        return plan_copy

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def generate_test_steps(
        self,
        user_instruction: str,
        force_fresh: bool = False,
    ) -> Dict:
        """
        Generate a test plan for the given instruction.

        Args:
            user_instruction: Natural-language test description.
            force_fresh: When True, skip the RAG workflow cache entirely and
                         always ask the LLM to produce a brand-new plan.
        """
        query_domain = extract_domain_from_text(user_instruction)
        
        # 🔥 Auto-detect if we need a fresh plan based on instruction complexity
        auto_force_fresh = self._needs_fresh_plan(user_instruction)
        effective_force_fresh = force_fresh or auto_force_fresh
        
        logger.info(
            f"[LLMService] Generating test plan | "
            f"domain='{query_domain}' | "
            f"force_fresh={force_fresh} | "
            f"auto_force_fresh={auto_force_fresh} | "
            f"effective_force_fresh={effective_force_fresh} | "
            f"instruction='{user_instruction[:80]}'"
        )

        # 1. Check RAG for a parameterized workflow (skip if effective_force_fresh)
        if not effective_force_fresh:
            rag_steps, metadata = self._rag.find_similar_workflow_parameterized(
                user_instruction, force_fresh=False
            )
            
            if rag_steps:
                # Verify RAG steps have required actions
                if self._rag_steps_sufficient(rag_steps, user_instruction):
                    logger.info(
                        f"[LLMService] ✅ Reusing and parameterizing workflow from RAG "
                        f"(domain='{query_domain}', steps={len(rag_steps)})."
                    )
                    if metadata.get("parameterized"):
                        logger.info(
                            f"[LLMService] ✓ Parameterized: '{metadata['old_term']}' → "
                            f"'{metadata['new_term']}'"
                        )
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
                else:
                    logger.warning(f"[LLMService] ⚠️ RAG workflow insufficient, forcing fresh plan")
                    effective_force_fresh = True
        else:
            if force_fresh:
                logger.info("[LLMService] force_fresh=True — skipping RAG workflow lookup.")
            elif auto_force_fresh:
                logger.info("[LLMService] auto_force_fresh=True — extra actions detected, skipping RAG.")

        # 2. Build RAG-enhanced prompt (with force_fresh context if needed)
        rag_context = self._rag.get_context_for_prompt(
            user_instruction,
            force_fresh=effective_force_fresh,
        )
        prompt = self._build_prompt(user_instruction, rag_context)

        # 3. First LLM call
        llm_available = True
        try:
            raw = self._call_ollama(prompt)
            logger.debug(f"[LLMService] Raw response:\n{raw[:500]}")
        except Exception as e:
            llm_available = False
            logger.error(f"[LLMService] Ollama call failed: {e}")
            logger.warning("[LLMService] ⚠️ Using fallback because LLM is unavailable")
            return self._fallback_result(user_instruction, str(e))

        test_plan, was_repaired = debug_agent.fix_test_plan(raw, instruction=user_instruction)
        if test_plan:
            logger.info(
                f"[LLMService] Plan parsed (repaired={was_repaired}), "
                f"steps={len(test_plan.get('steps', []))}"
            )
            test_plan = self._force_search_term_override(test_plan, user_instruction)
            test_plan, issues = validate_and_repair_plan(test_plan, user_instruction)
            return {
                "success": True,
                "test_plan": test_plan,
                "error": None,
                "was_repaired": was_repaired or bool(issues),
                "validation_issues": issues,
            }

        # 4. Retry with strict prompt
        logger.warning("[LLMService] First parse failed — retrying with strict JSON prompt.")
        try:
            raw2 = self._call_ollama(self._build_strict_prompt(user_instruction))
            test_plan, was_repaired = debug_agent.fix_test_plan(
                raw2, instruction=user_instruction
            )
        except Exception as e:
            logger.error(f"[LLMService] Retry failed: {e}")
            logger.warning("[LLMService] ⚠️ Using fallback because LLM is unavailable")
            test_plan = None

        if test_plan:
            logger.info("[LLMService] Plan recovered on retry.")
            test_plan = self._force_search_term_override(test_plan, user_instruction)
            test_plan, issues = validate_and_repair_plan(test_plan, user_instruction)
            return {
                "success": True,
                "test_plan": test_plan,
                "error": None,
                "was_repaired": True,
                "validation_issues": issues,
            }

        # 5. Ultimate fallback
        logger.error("[LLMService] All parse attempts failed — using fallback plan.")
        if not llm_available:
            logger.warning("[LLMService] ⚠️ Using fallback because LLM is unavailable")
        return self._fallback_result(user_instruction, "LLM returned unparseable JSON")

    # ------------------------------------------------------------------
    # Selector healing via LLM
    # ------------------------------------------------------------------

    def fix_selector_via_llm(self, failed_step: Dict, error_message: str) -> Optional[str]:
        prompt = (
            f"A browser automation step failed. Suggest ONE better CSS selector.\n\n"
            f"Action: {failed_step.get('action')}\n"
            f"Description: {failed_step.get('description')}\n"
            f"Current selector: {failed_step.get('selector')}\n"
            f"Error: {error_message}\n\n"
            f"Reply with ONLY a valid CSS selector. No explanation, no quotes, no markdown.\n"
            f"Examples:\n"
            f"  textarea[name='q']\n"
            f"  input[id='twotabsearchtextbox']\n"
            f"  button[type='submit']\n"
            f"Selector:"
        )
        try:
            raw = self._call_ollama(prompt, max_tokens=60, temperature=0.0).strip().strip('"\'`')
            if raw and len(raw) < 200 and not raw.startswith("{"):
                logger.info(f"[LLMService] LLM suggested selector: '{raw}'")
                return raw
        except Exception as e:
            logger.warning(f"[LLMService] Selector LLM call failed: {e}")

        return debug_agent.suggest_alternative_selector(
            failed_step.get("selector", ""),
            failed_step.get("description", ""),
            failed_step.get("action", ""),
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "ping",
                    "stream": False,
                    "options": {"num_predict": 1, "temperature": 0},
                },
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Ollama HTTP call
    # ------------------------------------------------------------------

    def _call_ollama(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
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
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_prompt(self, instruction: str, rag_context: str = "") -> str:
        rag_section = ""
        if rag_context:
            rag_section = f"""
RELEVANT PAST EXPERIENCE (use as hints):
{rag_context}
"""

        return f"""You are an expert browser automation AI assistant. Convert the natural language instruction below into a precise JSON test plan.

User Instruction: "{instruction}"
{rag_section}
Output a JSON object with this exact structure:
{{
  "url": "<base URL or null>",
  "steps": [
    {{
      "action": "navigate|click|fill|press|wait|assert|download|scroll|hover|select|extract",
      "description": "Human-readable description",
      "selector": "CSS selector (only for click/fill/assert/hover/select/extract)",
      "value": "Input value (for fill/select) — IMPORTANT: This must be ONLY the search keyword, not the full instruction fragment",
      "url": "Target URL (for navigate only)",
      "key": "Key name (for press only, e.g. Enter, Tab)",
      "assertion_type": "visible|text_contains|url_contains|title_contains|count_gt",
      "expected": "Expected value (for assert)",
      "duration": 2000,
      "direction": "down|up (for scroll only)",
      "amount": 300
    }}
  ]
}}

=== CRITICAL RULES ===

SEARCH VALUE RULE:
- When filling a search box, the 'value' field MUST contain ONLY the actual search keyword
- Example: For "Open Google and search for Narendra Modi" → value = "Narendra Modi"
- Example: For "Search for Python tutorials on Google" → value = "Python tutorials"
- Example: For "Search for weather in London on Google" → value = "weather in London"
- DO NOT include phrases like "and search for" or the full instruction in the value field

GOOGLE SEARCH WORKFLOW:
1. navigate → https://www.google.com
2. wait 2000ms (let page settle)
3. fill → selector: textarea[name='q'] — NEVER use input[name='q']
4. press → key: Enter
5. wait 3000ms
6. [IF USER ASKS FOR IMAGES OR IMAGES TAB] click → Images tab: selector: a[href*='tbm=isch']
7. [IF USER ASKS FOR IMAGES] wait 2000ms
8. [IF USER ASKS FOR FIRST IMAGE] click first image → selector: img.Q4LuWd (or img)
9. [IF USER ASKS FOR DOWNLOAD] download

AMAZON WORKFLOW:
1. navigate → https://www.amazon.in
2. wait 2000ms
3. fill → selector: input[id='twotabsearchtextbox']
4. press → key: Enter
5. wait 3000ms
6. [IF USER ASKS TO CLICK PRODUCT] click product → selector: div[data-component-type='s-search-result'] h2 a
7. [IF USER ASKS TO ADD TO CART] click Add to Cart → selector: input#add-to-cart-button, #add-to-cart-button, input[name='submit.add-to-cart']

GENERAL RULES:
- Always start with a navigate step unless instruction says to use current page
- Add wait steps after navigate (2000ms) and after press/search (3000ms)
- Use descriptive 'description' fields — they help with debugging
- Do NOT include selectors for: navigate, wait, press, download steps
- Keep selector as null/omit it if not applicable
- Return ONLY valid JSON — no markdown, no code fences, no explanation

Now generate the plan for: "{instruction}"
Return ONLY valid JSON:"""

    def _build_strict_prompt(self, instruction: str) -> str:
        return (
            f"Output ONLY a valid JSON object. No markdown. No explanation. No code fences.\n\n"
            f'Task: "{instruction}"\n\n'
            f"Rules: textarea[name='q'] for Google search. Add wait steps. Valid JSON only.\n\n"
            f'{{"url": null, "steps": ['
            f'{{"action": "navigate", "description": "Open Google", "url": "https://www.google.com"}}, '
            f'{{"action": "wait", "description": "Wait for load", "duration": 2000}}, '
            f'{{"action": "fill", "description": "Enter search term", "selector": "textarea[name=\'q\']", "value": "SEARCH_TERM"}}, '
            f'{{"action": "press", "description": "Submit", "key": "Enter"}}, '
            f'{{"action": "wait", "description": "Wait for results", "duration": 3000}}'
            f"]}}\n\nComplete JSON for the task:"
        )

    # ------------------------------------------------------------------
    # Fallback plan - Uses GLOBAL extractor (no duplicate logic)
    # ------------------------------------------------------------------

    def _fallback_result(self, instruction: str, error: str) -> Dict:
        plan = self._build_fallback_plan(instruction)
        plan, issues = validate_and_repair_plan(plan, instruction)
        return {
            "success": True,
            "test_plan": plan,
            "error": f"LLM parse failed ({error}); using auto-generated fallback.",
            "was_repaired": True,
            "validation_issues": issues,
        }

    def _build_fallback_plan(self, instruction: str) -> Dict:
        """Intelligent fallback plan inference from instruction keywords."""
        instr_lower = instruction.lower()
        
        # 🔥 USE GLOBAL EXTRACTOR - SINGLE SOURCE OF TRUTH
        search_term = extract_search_term(instruction)
        
        if not search_term:
            # Ultimate fallback: take last meaningful word
            words = [w for w in instruction.split() if len(w) > 2 and w.lower() not in 
                    ('the', 'and', 'for', 'with', 'from', 'google', 'amazon', 'search', 'find')]
            search_term = words[-1] if words else "search"
        
        logger.info(f"[LLMService] Fallback using search term: '{search_term}'")
        
        if "amazon" in instr_lower:
            return self._fallback_amazon(instruction, search_term)
        
        # Default: Google
        return self._fallback_google(instruction, search_term)

    def _fallback_google(self, instruction: str, search_term: str) -> Dict:
        """Generate Google fallback plan with clean search term."""
        # Improved detection with word boundaries
        has_images = bool(re.search(r"\bimages?\b", instruction, re.IGNORECASE) or 
                         re.search(r"\bpictures?\b", instruction, re.IGNORECASE) or
                         re.search(r"\bphotos?\b", instruction, re.IGNORECASE) or
                         "images tab" in instruction.lower())
        has_download = bool(re.search(r"\bdownload\b", instruction, re.IGNORECASE) or 
                           re.search(r"\bsave\b", instruction, re.IGNORECASE))
        
        steps = [
            {"action": "navigate", "description": "Navigate to Google", "url": "https://www.google.com"},
            {"action": "wait", "description": "Wait for Google to load", "duration": 2000},
            {"action": "fill", "description": f"Search for '{search_term}'",
             "selector": "textarea[name='q']", "value": search_term},
            {"action": "press", "description": "Submit search", "key": "Enter"},
            {"action": "wait", "description": "Wait for results", "duration": 3000},
        ]
        
        if has_images:
            steps += [
                {"action": "click", "description": "Click Images tab", "selector": "a[href*='tbm=isch']"},
                {"action": "wait", "description": "Wait for images", "duration": 2000},
                {"action": "click", "description": "Click first image", "selector": "img.Q4LuWd"},
                {"action": "wait", "description": "Wait for image view", "duration": 2000},
            ]
            if has_download:
                steps.append({"action": "download", "description": "Download image"})
        
        logger.info(f"[LLMService] Google fallback plan: {len(steps)} steps, search_term='{search_term}', has_images={has_images}")
        return {"url": "https://www.google.com", "steps": steps}

    def _fallback_amazon(self, instruction: str, search_term: str) -> Dict:
        """Generate Amazon fallback plan with robust selectors and proper waits."""
        has_add_to_cart = bool(re.search(r"\badd to cart\b", instruction, re.IGNORECASE) or 
                              re.search(r"\bbuy\b", instruction, re.IGNORECASE) or
                              re.search(r"\bpurchase\b", instruction, re.IGNORECASE))
        has_click_product = bool(re.search(r"\bclick\b", instruction, re.IGNORECASE) or 
                                re.search(r"\bopen\b", instruction, re.IGNORECASE) or
                                re.search(r"\bselect\b", instruction, re.IGNORECASE))
        
        # Base steps - always included
        steps = [
            {"action": "navigate", "description": "Navigate to Amazon India", "url": "https://www.amazon.in"},
            {"action": "wait", "description": "Wait for Amazon homepage to load", "duration": 3000},
            {"action": "fill", "description": f"Search for '{search_term}' in Amazon search box",
             "selector": "input[id='twotabsearchtextbox']", "value": search_term},
            {"action": "press", "description": "Press Enter to submit search", "key": "Enter"},
            {"action": "wait", "description": "Wait for search results to load completely", "duration": 5000},
        ]
        
        # Click on first product if requested
        if has_click_product:
            steps += [
                {"action": "click", "description": "Click on the first product in search results", 
                 "selector": "div[data-component-type='s-search-result'] h2 a"},
                {"action": "wait", "description": "Wait for product detail page to load", "duration": 4000},
            ]
        
        # Add to cart if requested
        if has_add_to_cart:
            steps += [
                {"action": "click", "description": "Click the Add to Cart button",
                 "selector": "input#add-to-cart-button, #add-to-cart-button, input[name='submit.add-to-cart']"},
                {"action": "wait", "description": "Wait for cart to update", "duration": 3000},
            ]
        
        logger.info(f"[LLMService] Amazon fallback plan: {len(steps)} steps, search_term='{search_term}', "
                    f"has_click_product={has_click_product}, has_add_to_cart={has_add_to_cart}")
        return {"url": "https://www.amazon.in", "steps": steps}


# Singleton
llm_service = LLMService()
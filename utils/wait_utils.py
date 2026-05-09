# utils/wait_utils.py
import asyncio
from typing import Optional
from playwright.async_api import Page


async def wait_for_page_stable(
    page: Page, 
    network_idle_timeout: int = 5000,
    dom_stable_ms: int = 500
) -> bool:
    """Wait for page to become stable using event-driven checks."""
    
    try:
        # Wait for network to be idle
        await page.wait_for_load_state("networkidle", timeout=network_idle_timeout)
    except Exception:
        pass  # Continue even if network idle times out
    
    # Wait for DOM mutations to settle using mutation observer
    try:
        await page.evaluate(f"""
            new Promise((resolve) => {{
                let timeout = setTimeout(resolve, {dom_stable_ms});
                const observer = new MutationObserver(() => {{
                    clearTimeout(timeout);
                    timeout = setTimeout(resolve, {dom_stable_ms});
                }});
                observer.observe(document.body, {{
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['class', 'style', 'hidden']
                }});
                setTimeout(() => observer.disconnect(), {dom_stable_ms * 2});
            }})
        """)
    except Exception:
        await asyncio.sleep(0.3)  # Fallback small delay
    
    return True


async def wait_for_visual_stability(page: Page, timeout_ms: int = 3000) -> bool:
    """Wait for visual stability using screenshot comparison."""
    try:
        start_time = asyncio.get_event_loop().time()
        last_hash = None
        
        while (asyncio.get_event_loop().time() - start_time) * 1000 < timeout_ms:
            screenshot = await page.screenshot(type="png")
            current_hash = hash(screenshot)
            
            if last_hash == current_hash:
                return True
            
            last_hash = current_hash
            await asyncio.sleep(0.3)
        
        return False
    except Exception:
        await asyncio.sleep(0.5)
        return True
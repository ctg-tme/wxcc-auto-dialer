import asyncio
import time

async def poll_for_element(page, selectors, timeout_seconds=10, interval_seconds=0.5):
    """Poll for an element to appear"""
    end_time = time.time() + timeout_seconds
    while time.time() < end_time:
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0 and await locator.is_visible():
                    return locator
            except Exception:
                pass
        await asyncio.sleep(interval_seconds)
    return None

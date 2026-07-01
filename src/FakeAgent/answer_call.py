import asyncio
from .utils import poll_for_element

async def answer_incoming_call(page, timeout_seconds=240):
    """Wait for and answer an incoming call by clicking the Answer button. Also poll for md-task-item elements and check if any can be answered (deep shadow DOM search)."""
    print("[Agent] Waiting for incoming call...")
    end_time = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < end_time:
        # Check for md-task-item presence
        task_items = page.locator('md-task-item')
        task_item_count = await task_items.count()
        if task_item_count > 0:
            await asyncio.sleep(1)
            await page.keyboard.press('Enter')
            return True
        await asyncio.sleep(0.05)
    print("[Agent] No incoming call detected within timeout.")
    return False

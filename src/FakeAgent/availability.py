import asyncio
from .utils import poll_for_element


async def _first_visible(locator, timeout_seconds=5, interval_seconds=0.2, max_matches=20):
    end_time = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < end_time:
        try:
            count = min(await locator.count(), max_matches)
            for index in range(count):
                element = locator.nth(index)
                if await element.is_visible():
                    return element
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
    return None


async def _activate_element(page, locator, label):
    try:
        await locator.click(timeout=3000)
        return True
    except Exception as exc:
        print(f"[Agent] Normal click failed for {label}: {exc!s}. Trying keyboard activation.")

    try:
        await locator.focus()
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.3)
    except Exception as exc:
        print(f"[Agent] Keyboard activation failed for {label}: {exc!s}. Trying DOM click.")

    try:
        await locator.dispatch_event("click")
        return True
    except Exception as exc:
        print(f"[Agent] DOM click failed for {label}: {exc!s}.")
        return False


async def check_availability_state(page):
    """Check the current availability state using md-button.agent-state-button."""
    current_state = await _first_visible(
        page.locator('[data-testid="current-state-name"]'),
        timeout_seconds=2
    )
    if current_state:
        state_text = (await current_state.inner_text()).strip().lower()
        if "available" in state_text:
            return "available"
        if "engaged" in state_text:
            return "engaged"
        if state_text:
            return state_text

    primary_channel = await _first_visible(
        page.locator('[data-testid="primary-channel-avatar"]'),
        timeout_seconds=2
    )
    if primary_channel:
        label = (await primary_channel.get_attribute("label") or "").lower()
        if "available" in label:
            return "available"
        if "engaged" in label:
            return "engaged"

    md_button = await poll_for_element(
        page,
        ['md-button.agent-state-button'],
        timeout_seconds=10
    )
    if md_button:
        variant = await md_button.get_attribute('variant')
        return variant
    return None


async def _set_available_via_state_selector(page):
    """Set availability with the current granular state selector."""
    button = await _first_visible(
        page.locator('[data-testid="state-selector-button"], md-button.agent-state-button'),
        timeout_seconds=10
    )
    if not button:
        return False

    if not await _activate_element(page, button, "state selector button"):
        return False
    await asyncio.sleep(0.3)

    available_option = await _first_visible(
        page.locator('[data-testid="set-all-channels-available"]'),
        timeout_seconds=5
    )
    if not available_option:
        return False

    print("[Agent] Selecting 'Set as Available (all channels)'.")
    if not await _activate_element(page, available_option, "set all channels available option"):
        return False
    await asyncio.sleep(1)
    return True


async def _set_available_via_keyboard(page, button):
    """Helper to set availability to 'available' using keyboard navigation."""
    await button.focus()
    await page.keyboard.press("Enter")
    await asyncio.sleep(1)
    await page.keyboard.press("Tab")
    await asyncio.sleep(0.2)
    await page.keyboard.press("ArrowDown")
    await asyncio.sleep(0.2)
    await page.keyboard.press("Enter")
    await asyncio.sleep(1)

async def set_availability_state(page, user_config, index, max_retries=2):
    """Set agent/supervisor availability state to Available using keyboard shortcuts, with retries."""
    # First, check the current state
    variant = await check_availability_state(page)
    print(f"[{user_config['role']}] Current availability: {variant}")
    if variant == "available":
        print(f"[{user_config['role']}] Already available, no action needed.")
        return variant
    if variant == "engaged":
        print(f"[{user_config['role']}] Agent is engaged. No action taken.")
        return variant
    for attempt in range(max_retries):
        if await _set_available_via_state_selector(page):
            new_variant = await check_availability_state(page)
            if new_variant == "available":
                return "available"
            print(f"[{user_config['role']}] Availability not set via state selector, retrying ({attempt+1}/{max_retries})...")
    # Use the old flow to set the state
    button = await poll_for_element(
        page,
        ['button[aria-label*="Availability State"]'],
        timeout_seconds=10
    )
    if button:
        print(f"[{user_config['role']}] Found availability button, clicking...")
        for attempt in range(max_retries):
            await _set_available_via_keyboard(page, button)
            new_variant = await check_availability_state(page)
            if new_variant == "available":
                return "available"
            else:
                print(f"[{user_config['role']}] Availability not set, retrying ({attempt+1}/{max_retries})...")
        # Final check after retries
        final_variant = await check_availability_state(page)
        return final_variant
    else:
        print(f"[{user_config['role']}] Availability button not found")
        return variant

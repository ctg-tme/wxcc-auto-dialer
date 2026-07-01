import asyncio
import os


WRAP_UP_MODES = {"auto", "legacy", "suggested"}


async def _wait_for_debug(reason: str) -> None:
    print(f"[Agent] Wrap up failed: {reason}. Pausing for debug (Ctrl+C to exit).")
    await asyncio.Event().wait()


async def _get_active_element_info(page):
    return await page.evaluate(
        """() => {
            const frameChain = [];
            let crossOriginFrame = null;
            const getDeepActiveElement = (root) => {
                let active = root.activeElement;
                while (active) {
                    if (active.shadowRoot && active.shadowRoot.activeElement) {
                        active = active.shadowRoot.activeElement;
                        continue;
                    }
                    if (active.tagName && active.tagName.toLowerCase() === "iframe") {
                        const frameInfo = {
                            name: active.getAttribute("name"),
                            src: active.getAttribute("src")
                        };
                        frameChain.push(frameInfo);
                        try {
                            const doc = active.contentDocument;
                            if (doc && doc.activeElement) {
                                active = doc.activeElement;
                                continue;
                            }
                        } catch (error) {
                            crossOriginFrame = frameInfo;
                        }
                    }
                    break;
                }
                return active;
            };
            const active = getDeepActiveElement(document);
            const ariaActiveDescendantId = active
                ? active.getAttribute("aria-activedescendant")
                : null;
            let ariaActiveDescendantLabel = null;
            if (ariaActiveDescendantId) {
                const descendant = document.getElementById(ariaActiveDescendantId);
                if (descendant) {
                    ariaActiveDescendantLabel = descendant.getAttribute("aria-label");
                    if (!ariaActiveDescendantLabel && descendant.textContent) {
                        ariaActiveDescendantLabel = descendant.textContent.trim().slice(0, 80);
                    }
                }
            }
            return {
                id: active ? active.id || null : null,
                ariaLabel: active ? active.getAttribute("aria-label") : null,
                tag: active ? active.tagName.toLowerCase() : null,
                role: active ? active.getAttribute("role") : null,
                ariaActiveDescendantId,
                ariaActiveDescendantLabel,
                frameChain,
                crossOriginFrame
            };
        }"""
    )

def _format_active_element_info(info):
    element_id = info.get("id")
    aria_label = info.get("ariaLabel")
    tag = info.get("tag")
    role = info.get("role")
    active_descendant_id = info.get("ariaActiveDescendantId")
    active_descendant_label = info.get("ariaActiveDescendantLabel")
    frame_chain = info.get("frameChain") or []
    cross_origin_frame = info.get("crossOriginFrame")
    parts = [
        f"id={element_id!r}",
        f"aria-label={aria_label!r}",
        f"tag={tag!r}",
        f"role={role!r}",
    ]
    if active_descendant_id:
        parts.append(f"active-descendant={active_descendant_id!r}")
    if active_descendant_label:
        parts.append(f"active-descendant-label={active_descendant_label!r}")
    if frame_chain:
        parts.append(f"frame-chain={frame_chain!r}")
    if cross_origin_frame:
        parts.append(f"cross-origin-frame={cross_origin_frame!r}")
    return " ".join(parts)


async def _press_and_log_focus(page, key, log_delay=0.2, cooldown_delay=None, previous_info=None):
    if previous_info is None:
        previous_info = await _get_active_element_info(page)
    await page.keyboard.press(key)
    await asyncio.sleep(log_delay)
    info = await _get_active_element_info(page)
    label = "Shift+Tab" if key == "Shift+Tab" else key
    prev_formatted = _format_active_element_info(previous_info)
    curr_formatted = _format_active_element_info(info)
    status = "changed" if info != previous_info else "unchanged"
    print(
        f"[Agent] {label} focus after {log_delay:.1f}s ({status}): {curr_formatted} (prev {prev_formatted})"
    )
    if cooldown_delay and cooldown_delay > log_delay:
        await asyncio.sleep(cooldown_delay - log_delay)
    return info


def _get_wrap_up_mode():
    mode = os.getenv("WRAP_UP_MODE", "auto").strip().lower()
    if mode not in WRAP_UP_MODES:
        print(f"[Agent] Unknown WRAP_UP_MODE={mode!r}; using auto.")
        return "auto"
    return mode


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
        await locator.focus(timeout=3000)
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.2)
        return True
    except Exception as exc:
        print(f"[Agent] Keyboard activation failed for {label}: {exc!s}. Trying DOM click.")

    try:
        await locator.dispatch_event("click")
        return True
    except Exception as exc:
        print(f"[Agent] DOM click failed for {label}: {exc!s}.")
        return False


async def _wrapup_surface_visible(page):
    return bool(await _first_visible(
        page.locator(
            "#wrapup-button-id, "
            "#wrapup-suggested-reasons-dropdown-id-input, "
            "#wrapup-submit-button-id, "
            "[aria-label='Wrap Up List Container']"
        ),
        timeout_seconds=1,
    ))


async def _end_button_visible(page):
    return bool(await _first_visible(
        page.locator("[aria-label*='End']"),
        timeout_seconds=1,
    ))


async def _activate_end_call_button(page, attempts=4):
    for attempt in range(attempts):
        button = await _first_visible(
            page.locator("[aria-label*='End']"),
            timeout_seconds=2,
        )
        if not button:
            if await _wrapup_surface_visible(page):
                print("[Agent] End button gone and wrap up is visible.")
                return True
            print(f"[Agent] End button not visible on attempt {attempt + 1}/{attempts}.")
            await asyncio.sleep(0.5)
            continue

        print(f"[Agent] Activating End button (attempt {attempt + 1}/{attempts}).")
        try:
            await button.click(timeout=2000)
        except Exception as exc:
            print(f"[Agent] End button click attempt failed: {exc!s}")
            try:
                await button.dispatch_event("click", timeout=2000)
            except Exception as dispatch_exc:
                print(f"[Agent] End button DOM click attempt failed: {dispatch_exc!s}")

        await asyncio.sleep(0.75)
        if await _wrapup_surface_visible(page):
            return True
        if not await _end_button_visible(page):
            print("[Agent] End button disappeared but wrap up is not visible yet; retrying.")

    return False


async def _open_wrapup_reasons(page):
    already_open = await _first_visible(
        page.locator(
            "#wrapup-suggested-reasons-dropdown-id-input, "
            "[aria-label='Wrap Up List Container'], "
            "#wrapup-submit-button-id"
        ),
        timeout_seconds=1,
    )
    if already_open:
        return True

    wrapup_button = await _first_visible(
        page.locator("md-button#wrapup-button-id, button#wrapup-button-id, [data-testid='wrapup-button-id']"),
        timeout_seconds=5,
    )
    if not wrapup_button:
        wrapup_button = await _first_visible(
            page.get_by_role("button", name="Wrap Up Reasons"),
            timeout_seconds=2,
        )
    if not wrapup_button:
        print("[Agent] 'Wrap Up Reasons' button NOT found.")
        return False

    print("[Agent] Opening Wrap Up Reasons.")
    if not await _activate_element(page, wrapup_button, "wrap up reasons button"):
        return False
    await asyncio.sleep(0.3)
    return True


async def _submit_wrap_up(page):
    submit_button = await _first_visible(
        page.get_by_role("button", name="Submit Wrap Up"),
        timeout_seconds=5,
    )
    if not submit_button:
        submit_button = await _first_visible(
            page.locator("#wrapup-submit-button-id, [data-testid='wrapup-submit-testId']"),
            timeout_seconds=2,
        )
    if not submit_button:
        print("[Agent] 'Submit Wrap Up' button NOT found.")
        return False

    if not await _activate_element(page, submit_button, "submit wrap up button"):
        return False
    await asyncio.sleep(0.2)
    await page.keyboard.press("Escape")
    return True


async def _selected_suggested_wrapup_value(page):
    input_value = await page.locator("#wrapup-suggested-reasons-dropdown-id-input").evaluate(
        """input => input.value || input.getAttribute("value") || "" """
    )
    if input_value.strip():
        return input_value.strip()

    selected_option = await _first_visible(
        page.locator(".wrapup-picker__item[aria-selected='true']"),
        timeout_seconds=1,
    )
    if selected_option:
        return (
            await selected_option.get_attribute("title")
            or await selected_option.get_attribute("aria-label")
            or ""
        ).strip()

    return ""


async def _focus_wrapup_list_container(page, previous_info=None):
    if previous_info is None:
        previous_info = await _get_active_element_info(page)
    if previous_info.get("ariaLabel") == "Wrap Up List Container":
        return True
    info = await _press_and_log_focus(
        page, "Tab", log_delay=0.2, cooldown_delay=0.5, previous_info=previous_info
    )
    if info.get("ariaLabel") == "Wrap Up List Container":
        return True
    print("[Agent] Shift+Tab to recover focus.")
    info = await _press_and_log_focus(
        page, "Shift+Tab", log_delay=0.2, cooldown_delay=0.5, previous_info=info
    )
    await page.keyboard.press("Enter")
    await asyncio.sleep(0.2)
    info = await _press_and_log_focus(
        page, "Tab", log_delay=0.2, cooldown_delay=0.5, previous_info=info
    )
    return info.get("ariaLabel") == "Wrap Up List Container"


async def _handle_suggested_wrap_up(page):
    """Handle the suggested wrap-up UI by selecting any dropdown option."""
    print("[Agent] Trying suggested wrap up UI...")
    try:
        if not await _open_wrapup_reasons(page):
            return False

        search_input = await _first_visible(
            page.locator("#wrapup-suggested-reasons-dropdown-id-input"),
            timeout_seconds=3,
        )
        if not search_input:
            print("[Agent] Suggested wrap up search input not found.")
            return False

        await search_input.click()
        await asyncio.sleep(0.25)

        option = await _first_visible(
            page.locator(
                "#wrapup-suggested-reasons-dropdown-id-listbox [role='option'], "
                ".wrapup-picker__item[role='option']"
            ),
            timeout_seconds=2,
        )
        if not option:
            expand_button = await _first_visible(
                page.locator(".wrapup-picker__chevron-btn[aria-label='Expand']"),
                timeout_seconds=1,
            )
            if expand_button:
                await expand_button.click()
                await asyncio.sleep(0.25)
                option = await _first_visible(
                    page.locator(
                        "#wrapup-suggested-reasons-dropdown-id-listbox [role='option'], "
                        ".wrapup-picker__item[role='option']"
                    ),
                    timeout_seconds=2,
                )

        if option:
            label = await option.get_attribute("title") or await option.get_attribute("aria-label")
            print(f"[Agent] Selecting suggested wrap up option: {label or 'first visible option'}")
            if not await _activate_element(page, option, "suggested wrap up option"):
                return False
        else:
            print("[Agent] Suggested options not visible; selecting via keyboard fallback.")
            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.1)
            await page.keyboard.press("Enter")

        await asyncio.sleep(0.25)
        selected_value = await _selected_suggested_wrapup_value(page)
        if not selected_value:
            print("[Agent] Suggested wrap up option was not selected.")
            return False
        print(f"[Agent] Suggested wrap up selected: {selected_value}")
        if not await _submit_wrap_up(page):
            return False
    except Exception as exc:
        print(f"[Agent] Suggested wrap up failed ({exc!s}).")
        return False
    print("[Agent] Suggested wrap up complete.")
    return True


async def _handle_legacy_wrap_up(page):
    """Handle the legacy wrap-up UI with the existing keyboard flow."""
    print("[Agent] Trying legacy wrap up UI...")
    try:
        if not await _open_wrapup_reasons(page):
            return False
        info = await _get_active_element_info(page)
        if not await _focus_wrapup_list_container(page, previous_info=info):
            print("[Agent] Legacy wrap up list container not found.")
            return False
        await page.keyboard.press("ArrowDown")
        await asyncio.sleep(0.05)
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.25)
        if not await _submit_wrap_up(page):
            return False
    except Exception as exc:
        print(f"[Agent] Legacy wrap up failed ({exc!s}).")
        return False
    print("[Agent] Legacy wrap up complete.")
    return True


async def handle_wrap_up(page):
    """Handle wrap up across current and legacy WxCC desktop UI variants."""
    print("[Agent] Handling wrap up...")
    await asyncio.sleep(1.5)
    mode = _get_wrap_up_mode()

    if mode in {"auto", "suggested"} and await _handle_suggested_wrap_up(page):
        return True
    if mode == "suggested":
        await _wait_for_debug("suggested wrap up UI did not complete")
        return False

    if mode in {"auto", "legacy"} and await _handle_legacy_wrap_up(page):
        return True

    await _wait_for_debug("no wrap up UI variant completed")
    return False


async def end_call(page, timeout_seconds=10):
    """Find the 'End' button and press Enter on it. Print if found and pressed, then handle wrap up."""
    print("[Agent] Attempting to end the call...")
    if await _first_visible(page.locator("[aria-label*='End']"), timeout_seconds=timeout_seconds):
        print("[Agent] 'End' button found. Ending call.")
        if not await _activate_end_call_button(page):
            await _wait_for_debug("end call button could not be activated")
            return False
        if await handle_wrap_up(page):
            return True
        await _wait_for_debug("wrap up did not complete after ending the call")
        return False
    else:
        print("[Agent] 'End' button NOT found. Trying wrap up flow.")
        if await handle_wrap_up(page):
            return True
        await _wait_for_debug("wrap up did not complete without ending the call")
        return False

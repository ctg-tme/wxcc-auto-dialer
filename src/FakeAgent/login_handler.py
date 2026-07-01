import os
from .utils import poll_for_element
import asyncio
import time

AGENT_DESKTOP_URL = os.getenv("AGENT_DESKTOP_URL", "https://desktop.wxcc-eu2.cisco.com/")

async def handle_station_credentials(page, user_config, index, delay=10):
    """Handle the Station Credentials modal if it appears"""
    try:
        modal_selectors = [
            'md-modal[aria-label="Station Credentials"]',
            'md-modal h2:has-text("Station Credentials")'
        ]
        modal = await poll_for_element(
            page,
            modal_selectors,
            timeout_seconds=delay
        )
        if modal:
            await page.keyboard.press("Escape")
            await page.evaluate('''() => {
                document.querySelectorAll('md-popover, md-tooltip, .tooltip, .popover').forEach(p => {
                    if (p.style) p.style.display = 'none';
                    if (p.remove) p.remove();
                });
            }''')
            desktop_radio_selectors = [
                'md-radio[value="DESKTOP"]',
                'md-radio[arialabel="Desktop"]',
                'md-radio:has-text("Desktop")'
            ]
            radio = await poll_for_element(
                page,
                desktop_radio_selectors,
                timeout_seconds=3,
                interval_seconds=0.2
            )
            if radio:
                await radio.click()
            else:
                for _ in range(3):
                    await page.keyboard.press("Tab")
                await page.keyboard.press("ArrowRight")  
                await page.keyboard.press("ArrowRight") 
                await page.keyboard.press("Space")
            submit_selectors = [
                'md-button[arialabel="Submit"]',
                'md-button[variant="primary"]',
                'md-button:has-text("Submit")'
            ]
            submit_button = await poll_for_element(
                page,
                submit_selectors,
                timeout_seconds=3,
                interval_seconds=0.2
            )
            if submit_button and await submit_button.is_enabled():
                await submit_button.click()
            else:
                await page.evaluate('''() => {
                    const submitBtns = document.querySelectorAll('md-button[variant="primary"]');
                    for (const btn of submitBtns) {
                        if (btn.hasAttribute('disabled')) {
                            btn.removeAttribute('disabled');
                        }
                        btn.click();
                    }
                }''')
            await asyncio.sleep(2)
        else:
            modal = await poll_for_element(
                page,
                modal_selectors,
                timeout_seconds=5
            )
            if modal:
                try:
                    await page.keyboard.press("Escape")
                    radio = page.locator('md-radio[value="DESKTOP"]')
                    if await radio.count() > 0:
                        await radio.click()
                    await asyncio.sleep(0.5)
                    submit = page.locator('md-button[variant="primary"]')
                    if await submit.count() > 0:
                        await submit.click()
                except Exception as e:
                    print(f"Error on second check: {e}")
    except Exception as e:
        print(f"Error handling Station Credentials: {e}")
    return page

async def handle_login(page, user_config, index):
    """Handle the login process, including station credentials"""
    await page.goto(AGENT_DESKTOP_URL, wait_until="domcontentloaded", timeout=90000)
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    print(f"[{user_config['role']}] Logging in...")
    await page.fill('input[type="email"]', user_config['email'])
    await page.press('input[type="email"]', "Enter")

# --- DUO INLINE FLOW (no iframe) ---
    duo_root = await poll_for_element(
        page,
        ['#login-parent[data-secured-by-duo="True"]'],
        timeout_seconds=6
    )
    if duo_root:
        print(f"[{user_config['role']}] DUO SSO detected (inline).")

        # Email step
        duo_email = await poll_for_element(
            page,
            ['label.Card__TextInput:has(span.label:has-text("Email Address")) input[type="email"]'],
            timeout_seconds=6
        )
        if duo_email:
            await duo_email.fill(user_config['email'])

            # Wait for enabled "Next" (it starts disabled)
            await page.wait_for_selector(
                'button[type="button"]:has-text("Next"):not([disabled])',
                timeout=8000
            )
            await page.click('button[type="button"]:has-text("Next")')

        # Password step
        duo_password = await poll_for_element(
            page,
            ['label.Card__TextInput:has(span.label:has-text("Password")) input[type="password"]'],
            timeout_seconds=8
        )
        if duo_password:
            await duo_password.fill(user_config['password'])

            # Wait for enabled "Log in" (it starts disabled)
            await page.wait_for_selector(
                'button[type="submit"]:has-text("Log in"):not([disabled])',
                timeout=8000
            )
            await page.click('button[type="submit"]:has-text("Log in")')

        # Give DUO time to redirect back
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

    microsoft_login = False
    microsoft_element = await poll_for_element(
        page,
        ['input[name="loginfmt"]', 'div:has-text("Microsoft")'],
        timeout_seconds=3
    )
    if microsoft_element:
        microsoft_login = True
        await microsoft_element.fill(user_config['email'])
        submit_button = await poll_for_element(page, ['input[type="submit"]'], timeout_seconds=2)
        if submit_button:
            await submit_button.click()
    password_field = await poll_for_element(page, ['input[type="password"]'], timeout_seconds=5)
    if password_field:
        await password_field.fill(user_config['password'])
        if microsoft_login:
            submit_button = await poll_for_element(page, ['input[type="submit"]'], timeout_seconds=5)
            if submit_button:
                await submit_button.click()
                stay_button = await poll_for_element(
                    page,
                    ['input[type="submit"][value="Yes"]', 'input#idSIButton9', 'input[type="submit"][aria-describedby="KmsiDescription"]'],
                    timeout_seconds=4
                )
                if stay_button:
                    await stay_button.click()
        else:
            await password_field.press("Enter")
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await handle_station_credentials(page, user_config, index)

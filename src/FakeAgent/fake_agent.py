import asyncio
import sys
import os
import shutil
import tempfile
import subprocess
from playwright.async_api import async_playwright
from .login_handler import handle_login
from .availability import set_availability_state
from .answer_call import answer_incoming_call  # <-- Import the answer call function
from .end_call import end_call

AGENT_DESKTOP_URL = os.getenv("AGENT_DESKTOP_URL", "https://desktop.wxcc-eu2.cisco.com/")
AGENT_DESKTOP_ORIGIN = AGENT_DESKTOP_URL.rstrip("/")

USER = {
    "role": "Agent",
    "email": "bill.stokes@cumulusorg.com",
    "password": "@hYsq$82",
    "extension": "286270"
}

async def launch_browser(playwright, user_config, ready_for_call_event: asyncio.Event, call_answered_event: asyncio.Event):
    print(f"[{user_config['role']}] Launching browser...")
    context, page = await setup_browser_context(playwright, user_config)
    await handle_login(page, user_config, 0)
    return context, page

async def setup_browser_context(playwright, user_config):
    """Setup the browser context with appropriate settings"""
    user_data_dir = tempfile.mkdtemp(prefix=f"playwright_{user_config['role'].lower()}_")
    # Get audio file path from user_config or use default
    audio_file_path = user_config.get('audio_file', '/audio/agent-audio-panned.wav')

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
        ignore_https_errors=True,
        java_script_enabled=True,
        bypass_csp=True,
        accept_downloads=True,
        args=[
            "--incognito",
            "--no-sandbox",
            "--disable-extensions",
            f"--use-file-for-fake-audio-capture={audio_file_path}",
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream"
        ]
    )
    await context.grant_permissions(['microphone'], origin=AGENT_DESKTOP_ORIGIN)
    page = await context.new_page()
    return context, page

async def main():
    print("Starting agent session...")
    ready_for_call_event = asyncio.Event()
    call_answered_event = asyncio.Event()
    
    async with async_playwright() as playwright:
        await launch_browser(playwright, USER, ready_for_call_event, call_answered_event)
        print("Session active. Waiting for agent availability signal (SIGUSR1)... Press Ctrl+C to exit.")
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("Script completed normally.")
    except KeyboardInterrupt:
        print("\nScript terminated by user.")
    except Exception as e:
        print(f"Script terminated due to error: {e}")

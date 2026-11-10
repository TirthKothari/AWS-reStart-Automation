"""
Authentication and Browser Context Management for Canvas LMS.
Handles automated login, session verification, and anti-throttling persistent context initialization.
"""

import time
import asyncio
from playwright.async_api import BrowserContext as AsyncBrowserContext, Page as AsyncPage
from playwright.sync_api import BrowserContext as SyncBrowserContext, Page as SyncPage

from .config import (
    PROFILE_DIR,
    LOGIN_URL,
    COURSE_URL,
    load_credentials,
    ensure_directories,
)

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--no-sandbox",
]


# ==========================================
# Async Playwright Browser / Login
# ==========================================

async def create_async_browser_context(playwright_instance, headless: bool = False) -> AsyncBrowserContext:
    """Launches an async persistent Chromium browser context."""
    ensure_directories()
    context = await playwright_instance.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        viewport={"width": 1400, "height": 900},
        args=BROWSER_ARGS,
    )
    return context


async def ensure_async_canvas_login(page: AsyncPage):
    """Verifies and performs Canvas LMS login asynchronously."""
    username, password = load_credentials()
    await page.goto(COURSE_URL, wait_until="networkidle", timeout=60000)
    await asyncio.sleep(2)

    if "login" in page.url.lower():
        print(f"[AUTH] Entering credentials for {username}...", flush=True)
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_selector("#pseudonym_session_unique_id, input[name='pseudonym_session[unique_id]']", timeout=15000)
        await page.locator("#pseudonym_session_unique_id, input[name='pseudonym_session[unique_id]']").first.fill(username)
        await page.locator("#pseudonym_session_password, input[name='pseudonym_session[password]']").first.fill(password)

        remember = page.locator("#pseudonym_session_remember_me")
        if await remember.count() > 0:
            try:
                await remember.check()
            except Exception:
                pass

        print("[AUTH] Submitting login form...", flush=True)
        await page.locator("button:has-text('Log In'), input[type='submit'], button[type='submit']:visible").first.click()
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(3)
        await page.goto(COURSE_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

    print(f"[AUTH] Canvas session active: {await page.title()}", flush=True)


# ==========================================
# Sync Playwright Browser / Login
# ==========================================

def create_sync_browser_context(playwright_instance, headless: bool = False) -> SyncBrowserContext:
    """Launches a sync persistent Chromium browser context."""
    ensure_directories()
    context = playwright_instance.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        viewport={"width": 1400, "height": 900},
        args=BROWSER_ARGS,
    )
    return context


def ensure_sync_canvas_login(page: SyncPage):
    """Verifies and performs Canvas LMS login synchronously."""
    username, password = load_credentials()
    page.goto(COURSE_URL, wait_until="networkidle", timeout=60000)
    time.sleep(2)

    if "login" in page.url.lower():
        print(f"[AUTH] Entering credentials for {username}...", flush=True)
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("#pseudonym_session_unique_id, input[name='pseudonym_session[unique_id]']", timeout=15000)
        page.locator("#pseudonym_session_unique_id, input[name='pseudonym_session[unique_id]']").first.fill(username)
        page.locator("#pseudonym_session_password, input[name='pseudonym_session[password]']").first.fill(password)

        remember = page.locator("#pseudonym_session_remember_me")
        if remember.count() > 0:
            try:
                remember.check()
            except Exception:
                pass

        print("[AUTH] Submitting login form...", flush=True)
        page.locator("button:has-text('Log In'), input[type='submit'], button[type='submit']:visible").first.click()
        page.wait_for_load_state("networkidle", timeout=60000)
        time.sleep(3)
        page.goto(COURSE_URL, wait_until="networkidle", timeout=60000)
        time.sleep(2)

    print(f"[AUTH] Canvas session active: {page.title()}", flush=True)

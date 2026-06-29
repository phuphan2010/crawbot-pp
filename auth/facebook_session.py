import asyncio
import time
from pathlib import Path

from loguru import logger
from playwright.async_api import BrowserContext, Page

from config import settings
from scrapers.browser import save_debug_screenshot


def _is_cookie_fresh(cookie_path: Path, max_age_days: int) -> bool:
    if not cookie_path.exists():
        return False
    age_days = (time.time() - cookie_path.stat().st_mtime) / 86400
    return age_days < max_age_days


async def _is_logged_in(page: Page) -> bool:
    try:
        await page.goto("https://www.facebook.com/", timeout=30000)
        await page.wait_for_load_state("domcontentloaded")
        # Check for the profile/account nav element that only appears when logged in
        logged_in = await page.locator('[aria-label="Your profile"]').count()
        if not logged_in:
            logged_in = await page.locator('[data-testid="royal_login_button"]').count() == 0
        return bool(logged_in)
    except Exception:
        return False


async def _do_login(page: Page, email: str, password: str) -> None:
    logger.info("Starting Facebook login flow...")
    await page.goto("https://www.facebook.com/login", timeout=30000)
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(1)

    # Use type() not fill() — simulates real keystrokes so React's onChange fires
    email_field = page.locator('[name="email"]')
    await email_field.click()
    await email_field.type(email, delay=40)

    pass_field = page.locator('[name="pass"]')
    await pass_field.click()
    await pass_field.type(password, delay=40)
    await asyncio.sleep(0.5)

    # Click login button — Playwright will timeout waiting for FB's redirect chain,
    # but the click still happens; we catch the error and wait separately
    try:
        await page.locator('[name="login"]').click(timeout=8000)
    except Exception:
        pass

    # Wait until we leave /login regardless of how many redirects FB does
    try:
        await page.wait_for_url(
            lambda url: "facebook.com" in url and "/login" not in url,
            timeout=60000,
        )
    except Exception:
        pass

    # Handle any verification pages in a loop (2FA, "Remember browser?", checkpoint)
    for _ in range(5):
        url = page.url
        logger.info(f"Current URL: {url}")

        if "remember_browser" in url:
            for btn_text in ["OK", "Continue", "Not now"]:
                try:
                    btn = page.get_by_role("button", name=btn_text)
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    pass
        elif "two_factor" in url or "two_step" in url or "checkpoint" in url:
            logger.warning("Facebook requires manual action (2FA / checkpoint).")
            logger.warning("Complete the steps in the browser window, then press ENTER here...")
            input("Press ENTER to continue: ")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
        else:
            break

        await asyncio.sleep(1)

    logger.info(f"Login flow done. Final URL: {page.url}")


async def ensure_session(ctx: BrowserContext, page: Page) -> None:
    """Ensure we have a valid Facebook session. Login if needed and save cookies."""
    cookie_path = settings.COOKIE_PATH
    cookie_path.parent.mkdir(parents=True, exist_ok=True)

    if _is_cookie_fresh(cookie_path, settings.COOKIE_MAX_AGE_DAYS):
        logger.info("Cookies are fresh — verifying session...")
        if await _is_logged_in(page):
            logger.info("Session valid. Proceeding without login.")
            return
        logger.warning("Cookies loaded but session appears invalid. Re-logging in...")

    await _do_login(page, settings.FB_EMAIL, settings.FB_PASSWORD)

    if not await _is_logged_in(page):
        await save_debug_screenshot(page, "login_failed")
        raise RuntimeError("Facebook login failed after attempt. Check credentials or screenshot in logs/debug/.")

    # Persist session
    await ctx.storage_state(path=str(cookie_path))
    logger.info(f"Session saved to {cookie_path}")

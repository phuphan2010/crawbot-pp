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

    await page.fill('[name="email"]', email)
    await page.fill('[name="pass"]', password)
    await page.click('[name="login"]')

    # Wait for redirect away from /login
    try:
        await page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    except Exception:
        pass

    # Handle 2FA or checkpoint — pause for manual intervention
    if "/checkpoint" in page.url or "/login" in page.url:
        logger.warning("Facebook requires additional verification (2FA / checkpoint).")
        logger.warning("Please complete verification in the browser window, then press ENTER here...")
        input("Press ENTER after completing verification: ")

    logger.info(f"Login complete. Current URL: {page.url}")


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

"""
Single-run entry point. Called by cron or manually.

Usage:
  python run_once.py                  # dùng HEADLESS setting trong .env
  xvfb-run -a python run_once.py     # chạy headful trên server không có display (lần đầu login)
"""
import asyncio
import sys
from datetime import date

from loguru import logger

from config import settings
from auth.facebook_session import ensure_session
from scrapers.browser import BrowserManager
from scrapers.group_scraper import scrape_group
from sheets.client import open_worksheet
from sheets.writer import append_posts
from utils.logger import setup_logger
from utils.helpers import async_random_delay, group_name_from_url


async def main() -> int:
    setup_logger(settings.LOG_LEVEL)
    logger.info("=== Facebook Group Scraper — starting run ===")

    browser = BrowserManager()
    use_cookies = settings.COOKIE_PATH.exists()

    await browser.start(headless=settings.HEADLESS, channel=settings.BROWSER_CHANNEL)

    ctx = await browser.new_context(cookie_path=settings.COOKIE_PATH if use_cookies else None)
    page = await ctx.new_page()

    try:
        await ensure_session(ctx, page)
    except RuntimeError as exc:
        logger.error(f"Session setup failed: {exc}")
        await browser.close()
        return 1

    today = date.today().isoformat()  # e.g. "2026-06-29"
    total_added = 0
    errors = 0

    for group_url in settings.GROUP_URLS:
        posts = await scrape_group(page, group_url)
        if len(settings.GROUP_URLS) > 1:
            await async_random_delay(1000, 3000)

        if not posts:
            logger.warning(f"No posts collected from {group_url}")
            continue

        sheet_name = f"{group_name_from_url(group_url)}_{today}"
        try:
            ws = open_worksheet(settings.SERVICE_ACCOUNT_JSON, settings.SHEET_ID, sheet_name)
            added = append_posts(ws, posts)
            logger.info(f"Sheet '{sheet_name}': {added} new posts added")
            total_added += added
        except Exception as exc:
            logger.exception(f"Google Sheets write failed for '{sheet_name}': {exc}")
            errors += 1

    await browser.close()

    logger.info(f"=== Run complete: {total_added} new posts added across all groups ===")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

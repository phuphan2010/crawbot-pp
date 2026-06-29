"""
Single-run entry point. Called by cron or manually.

Usage:
  python run_once.py                  # dùng HEADLESS setting trong .env
  xvfb-run -a python run_once.py     # chạy headful trên server không có display (lần đầu login)
"""
import asyncio
import sys

from loguru import logger

from config import settings
from auth.facebook_session import ensure_session
from scrapers.browser import BrowserManager
from scrapers.group_scraper import scrape_group
from sheets.client import open_worksheet
from sheets.writer import append_posts
from utils.logger import setup_logger
from utils.helpers import async_random_delay


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

    all_posts = []
    for group_url in settings.GROUP_URLS:
        posts = await scrape_group(page, group_url)
        all_posts.extend(posts)
        if len(settings.GROUP_URLS) > 1:
            await async_random_delay(1000, 3000)

    await browser.close()

    if not all_posts:
        logger.warning("No posts collected. Nothing to write.")
        return 0

    logger.info(f"Total posts collected across all groups: {len(all_posts)}")

    try:
        ws = open_worksheet(settings.SERVICE_ACCOUNT_JSON, settings.SHEET_ID, settings.WORKSHEET_NAME)
        added = append_posts(ws, all_posts)
        logger.info(f"=== Run complete: {added} new posts added to sheet ===")
    except Exception as exc:
        logger.error(f"Google Sheets write failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

import random
import re
from datetime import datetime, timedelta
from typing import List

from loguru import logger
from playwright.async_api import Page

from config import settings
from models.post import Post
from scrapers.browser import save_debug_screenshot
from scrapers.post_parser import parse_post
from utils.helpers import async_random_delay


# CSS selectors for post containers — Facebook changes these; update here when needed
POST_SELECTORS = [
    'div[data-pagelet^="FeedUnit"]',
    'div[role="article"]',
    'div[data-testid="post_container"]',
]

CHECKPOINT_PATTERNS = ["/checkpoint/", "/login/", "sorry"]


def _is_today_post(date_text: str) -> bool:
    """Return True if the relative date string indicates a post from today."""
    now = datetime.now()
    today = now.date()
    dt = date_text.lower().strip()
    if not dt or dt == "just now":
        return True
    m = re.match(r'^(\d+)([smhdw])$', dt)
    if not m:
        return True  # Unknown format (e.g. "June 10") — keep it
    value, unit = int(m.group(1)), m.group(2)
    deltas = {
        "s": timedelta(seconds=value),
        "m": timedelta(minutes=value),
        "h": timedelta(hours=value),
        "d": timedelta(days=value),
        "w": timedelta(weeks=value),
    }
    return (now - deltas[unit]).date() == today


async def _detect_issues(page: Page) -> str | None:
    """Return a description if a blocking page is detected, else None."""
    url = page.url
    for pattern in CHECKPOINT_PATTERNS:
        if pattern in url:
            return f"Blocking page detected: {url}"
    return None


async def scrape_group(page: Page, group_url: str) -> List[Post]:
    """Navigate to a group and collect posts via infinite scroll."""
    logger.info(f"Navigating to group: {group_url}")
    try:
        await page.goto(group_url, timeout=60000, wait_until="domcontentloaded")
    except Exception as exc:
        logger.error(f"Failed to navigate to {group_url}: {exc}")
        return []

    issue = await _detect_issues(page)
    if issue:
        await save_debug_screenshot(page, "group_issue")
        logger.error(issue)
        return []

    # Dismiss any cookie/notification dialogs
    for dismiss_selector in ['[aria-label="Close"]', '[data-testid="cookie-policy-dialog-accept-button"]']:
        try:
            btn = page.locator(dismiss_selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await async_random_delay(500, 1000)
        except Exception:
            pass

    # Wait for at least one post container to appear (replaces fixed delay).
    # Facebook renders feed via React — domcontentloaded fires before posts are in DOM.
    found_selector = None
    for selector in POST_SELECTORS:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            found_selector = selector
            logger.info(f"Feed ready (matched '{selector}')")
            break
        except Exception:
            continue

    if not found_selector:
        await save_debug_screenshot(page, "no_posts_found")
        logger.error("No post containers appeared within 20s — check debug screenshot")
        return []

    await async_random_delay(1000, 2000)

    all_posts: List[Post] = []
    seen_ids: set[str] = set()
    stall_count = 0
    max_stall = 3

    _dumped = False

    for scroll_num in range(1, settings.MAX_SCROLLS + 1):
        # Collect post elements using the selector that matched at load time
        post_elements = await page.query_selector_all(found_selector)
        if scroll_num == 1:
            logger.info(f"Scroll 1: {len(post_elements)} raw elements found by '{found_selector}'")

        # On first scroll, dump HTML of first 3 elements for selector debugging
        if scroll_num == 1 and not _dumped and post_elements:
            from pathlib import Path
            Path("logs/debug").mkdir(parents=True, exist_ok=True)
            for i, el in enumerate(post_elements[:3]):
                html = await el.inner_html()
                Path(f"logs/debug/article_{i}.html").write_text(html[:3000], encoding="utf-8")
            logger.info("Saved logs/debug/article_0..2.html for inspection")
            _dumped = True

        new_this_scroll = 0
        for el in post_elements:
            post = await parse_post(el, page)
            if post and post.post_id and post.post_id not in seen_ids:
                seen_ids.add(post.post_id)
                all_posts.append(post)
                new_this_scroll += 1

        logger.info(f"Scroll {scroll_num}/{settings.MAX_SCROLLS} — {new_this_scroll} new posts (total: {len(all_posts)})")

        if new_this_scroll == 0:
            stall_count += 1
            if stall_count >= max_stall:
                logger.info("No new posts after 3 consecutive scrolls — treating as end of feed")
                break
        else:
            stall_count = 0

        # Scroll down with randomised amount
        scroll_px = int(page.viewport_size["height"] * random.uniform(0.8, 1.3))
        await page.mouse.move(random.randint(200, 800), random.randint(200, 500))
        await page.evaluate(f"window.scrollBy(0, {scroll_px})")
        await async_random_delay(settings.SCROLL_PAUSE_MIN_MS, settings.SCROLL_PAUSE_MAX_MS)

        issue = await _detect_issues(page)
        if issue:
            await save_debug_screenshot(page, f"scroll_{scroll_num}_issue")
            logger.error(issue)
            break

    today_posts = [p for p in all_posts if _is_today_post(p.date)]
    logger.info(
        f"Finished scraping {group_url}: {len(today_posts)} today's posts "
        f"(filtered from {len(all_posts)} total)"
    )
    return today_posts

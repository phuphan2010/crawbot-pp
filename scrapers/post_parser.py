import re
from typing import List

from loguru import logger
from playwright.async_api import ElementHandle, Page

from models.post import Post
from utils.helpers import extract_post_id


async def _get_text(el: ElementHandle, selector: str, default: str = "") -> str:
    try:
        node = await el.query_selector(selector)
        return (await node.inner_text()).strip() if node else default
    except Exception:
        return default


async def _get_attr(el: ElementHandle, selector: str, attr: str) -> str:
    try:
        node = await el.query_selector(selector)
        return (await node.get_attribute(attr) or "").strip() if node else ""
    except Exception:
        return ""


async def _get_all_attrs(el: ElementHandle, selector: str, attr: str) -> List[str]:
    try:
        nodes = await el.query_selector_all(selector)
        results = []
        for n in nodes:
            val = await n.get_attribute(attr)
            if val:
                results.append(val.strip())
        return results
    except Exception:
        return []


async def parse_post(post_el: ElementHandle, page: Page) -> Post | None:
    """Parse a single Facebook post element into a Post dataclass."""
    try:
        # Author name: typically in a link near the top of the post
        author = await _get_text(post_el, 'h2 a, [data-testid="post_author"] a, strong a')
        if not author:
            # Fallback: find the first strong tag
            author = await _get_text(post_el, "strong")

        # Post timestamp link — href contains the canonical post URL
        timestamp_link = await post_el.query_selector('a[href*="/posts/"], a[href*="story_fbid"], a[href*="/permalink/"]')
        post_url = ""
        date_text = ""
        if timestamp_link:
            post_url = await timestamp_link.get_attribute("href") or ""
            # Make absolute
            if post_url.startswith("/"):
                post_url = "https://www.facebook.com" + post_url
            # Remove tracking params
            post_url = post_url.split("?")[0]
            date_text = (await timestamp_link.inner_text()).strip()

        post_id = extract_post_id(post_url) if post_url else ""

        # Post text content — look for the main text container
        text = ""
        for selector in [
            '[data-ad-comet-preview="message"]',
            '[data-testid="post_message"]',
            'div[dir="auto"] > span',
            'div[class*="userContent"]',
        ]:
            text = await _get_text(post_el, selector)
            if text:
                break

        # Image URLs
        image_urls: List[str] = []
        img_tags = await post_el.query_selector_all("img[src]")
        for img in img_tags:
            src = await img.get_attribute("src") or ""
            # Filter out profile pictures and icons (they tend to be small/cached URLs)
            if src and "scontent" in src and "emoji" not in src.lower():
                image_urls.append(src)

        # Video URLs — look for video source or data-video-id
        video_urls: List[str] = []
        video_els = await post_el.query_selector_all("video[src], [data-video-id]")
        for v in video_els:
            src = await v.get_attribute("src") or ""
            if src:
                video_urls.append(src)
            vid_id = await v.get_attribute("data-video-id") or ""
            if vid_id and not src:
                video_urls.append(f"https://www.facebook.com/video/embed?video_id={vid_id}")

        if not post_id and not text:
            return None

        return Post(
            post_id=post_id or text[:40],
            author=author,
            date=date_text,
            text=text,
            image_urls=image_urls,
            video_urls=video_urls,
            post_url=post_url,
        )

    except Exception as exc:
        logger.warning(f"Failed to parse post element: {exc}")
        return None

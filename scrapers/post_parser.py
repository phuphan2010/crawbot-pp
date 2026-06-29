import asyncio
import re
from typing import List

from loguru import logger
from playwright.async_api import ElementHandle, Page

from models.post import Post
from utils.helpers import extract_post_id

# Matches Facebook relative-time strings like "31m", "2h", "1d", "1w", "Just now"
_RELATIVE_TIME_RE = re.compile(r'^\d+[smhdw]$|^just\s*now$', re.I)


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
        # Author: modern FB uses a[href*="/user/"][aria-hidden="false"] for the name link.
        # inner_text() returns the visible name directly.
        author = await _get_text(post_el, 'a[href*="/user/"][aria-hidden="false"]')

        # Timestamp link — must have relative-time text AND must NOT be a comment link
        # (comment links contain "comment_id" in the href).
        post_url = ""
        date_text = ""
        for sel in ['a[href*="/posts/"]', 'a[href*="story_fbid"]', 'a[href*="/permalink/"]']:
            links = await post_el.query_selector_all(sel)
            for link in links:
                href = (await link.get_attribute("href")) or ""
                if "comment_id" in href:
                    continue
                txt = (await link.inner_text()).strip()
                if _RELATIVE_TIME_RE.match(txt):
                    if href.startswith("/"):
                        href = "https://www.facebook.com" + href
                    post_url = href.split("?")[0]
                    date_text = txt
                    break
            if post_url:
                break

        # Fallback: first post link regardless of time text
        if not post_url:
            links = await post_el.query_selector_all(
                'a[href*="/posts/"], a[href*="story_fbid"], a[href*="/permalink/"]'
            )
            for link in links:
                href = (await link.get_attribute("href")) or ""
                if "comment_id" in href:
                    continue
                if href.startswith("/"):
                    href = "https://www.facebook.com" + href
                post_url = href.split("?")[0]
                date_text = (await link.inner_text()).strip()
                break

        post_id = extract_post_id(post_url) if post_url else ""

        # Expand "See more" / "Xem thêm" so full text is in DOM
        try:
            buttons = await post_el.query_selector_all('[role="button"]')
            for btn in buttons:
                btn_text = (await btn.inner_text()).strip().lower()
                if btn_text in ("see more", "xem thêm"):
                    await btn.click()
                    await asyncio.sleep(0.3)
                    break
        except Exception:
            pass

        # Post text: span[dir="auto"][lang] wraps the entire post body including all paragraphs.
        # This is far more specific than div[dir="auto"] which appears all over the page.
        text = await _get_text(post_el, 'span[dir="auto"][lang]')

        # Image URLs — scontent*.fbcdn.net are user-uploaded images; static.xx.fbcdn.net are icons.
        image_urls: List[str] = []
        img_tags = await post_el.query_selector_all("img")
        for img in img_tags:
            src = await img.get_attribute("src") or ""
            if not src:
                src = await img.get_attribute("data-src") or ""
            if src and "scontent" in src and "fbcdn.net" in src and "emoji" not in src.lower():
                image_urls.append(src)

        # Video URLs
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

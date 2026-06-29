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


_debug_dumped = False  # dump HTML of only the first post per run


async def parse_post(post_el: ElementHandle, page: Page) -> Post | None:
    """Parse a single Facebook post element into a Post dataclass."""
    global _debug_dumped
    try:
        if not _debug_dumped:
            html = await post_el.inner_html()
            from pathlib import Path
            Path("logs/debug").mkdir(parents=True, exist_ok=True)
            Path("logs/debug/post_sample.html").write_text(html, encoding="utf-8")
            _debug_dumped = True
            logger.info("Debug HTML saved to logs/debug/post_sample.html")

        # Author name — try a cascade of selectors; modern FB often uses h2 > span > a
        author = ""
        for author_sel in [
            'h2 a',
            'h3 a',
            '[data-testid="post_author"] a',
            'strong a',
            'strong',
            'h2 span',
        ]:
            author = await _get_text(post_el, author_sel)
            if author and len(author) < 100:  # Skip if it grabbed too much text
                break

        # Find the timestamp link — its inner text is a relative-time string ("31m", "2h", …).
        # Using query_selector_all + filter avoids picking up post-body links whose visible
        # text is a full URL or long sentence.
        post_url = ""
        date_text = ""
        for sel in ['a[href*="/posts/"]', 'a[href*="story_fbid"]', 'a[href*="/permalink/"]']:
            links = await post_el.query_selector_all(sel)
            for link in links:
                txt = (await link.inner_text()).strip()
                if _RELATIVE_TIME_RE.match(txt):
                    href = (await link.get_attribute("href")) or ""
                    if href.startswith("/"):
                        href = "https://www.facebook.com" + href
                    post_url = href.split("?")[0]
                    date_text = txt
                    break
            if post_url:
                break

        # Fallback: take first matching link even without a recognised time string
        if not post_url:
            link = await post_el.query_selector(
                'a[href*="/posts/"], a[href*="story_fbid"], a[href*="/permalink/"]'
            )
            if link:
                href = (await link.get_attribute("href")) or ""
                if href.startswith("/"):
                    href = "https://www.facebook.com" + href
                post_url = href.split("?")[0]
                date_text = (await link.inner_text()).strip()

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

        # Post text content — try specific data attributes, then longest div[dir="auto"] block
        text = ""
        for selector in [
            '[data-ad-comet-preview="message"]',
            '[data-testid="post_message"]',
            '[data-ad-preview="message"]',
        ]:
            text = await _get_text(post_el, selector)
            if text:
                break

        if not text:
            try:
                nodes = await post_el.query_selector_all('div[dir="auto"]')
                candidates = []
                for n in nodes:
                    t = (await n.inner_text()).strip()
                    if len(t) > 10:
                        candidates.append(t)
                if candidates:
                    text = max(candidates, key=len)
            except Exception:
                pass

        # Image URLs — check both src and data-src (lazy-loaded images).
        # Only keep scontent*.fbcdn.net URLs — these are actual user-uploaded images.
        # static.xx.fbcdn.net/rsrc.php/... are UI icons and must be excluded.
        image_urls: List[str] = []
        img_tags = await post_el.query_selector_all("img")
        for img in img_tags:
            src = await img.get_attribute("src") or ""
            if not src:
                src = await img.get_attribute("data-src") or ""
            if src and "scontent" in src and "fbcdn.net" in src and "emoji" not in src.lower():
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

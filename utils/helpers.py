import asyncio
import functools
import random
import re
import time
from typing import Callable
from urllib.parse import urlparse, parse_qs

from loguru import logger


def group_name_from_url(group_url: str) -> str:
    """Extract group slug from a Facebook group URL for use as a sheet name."""
    m = re.search(r"/groups/([^/?#]+)", group_url)
    slug = m.group(1) if m else re.sub(r"[^\w]", "_", group_url)[-30:]
    # Sanitise: Sheets tab names cannot contain [ ] : * ? / \
    slug = re.sub(r'[\[\]:*?/\\]', "_", slug)
    return slug[:80]  # Sheets max tab name length is 100; leave room for date


def extract_post_id(url: str) -> str:
    """Extract a stable post identifier from a Facebook post URL."""
    url = url.split("?")[0].rstrip("/")
    # /groups/{group_id}/posts/{post_id}
    m = re.search(r"/posts/(\d+)", url)
    if m:
        return m.group(1)
    # /permalink.php?story_fbid={id}
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "story_fbid" in qs:
        return qs["story_fbid"][0]
    # fallback: last numeric segment
    segments = [s for s in url.split("/") if s.isdigit()]
    return segments[-1] if segments else url


def random_delay(min_ms: int, max_ms: int) -> None:
    """Synchronous random delay in milliseconds."""
    time.sleep(random.randint(min_ms, max_ms) / 1000)


async def async_random_delay(min_ms: int, max_ms: int) -> None:
    """Async random delay in milliseconds."""
    await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)


def retry(max_attempts: int = 3, delay: float = 5.0, backoff: float = 2.0):
    """Decorator for retrying a function on exception."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_attempts:
                        raise
                    logger.warning(f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {exc}. Retrying in {wait:.0f}s...")
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator


def async_retry(max_attempts: int = 3, delay: float = 5.0, backoff: float = 2.0):
    """Decorator for retrying an async function on exception."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_attempts:
                        raise
                    logger.warning(f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {exc}. Retrying in {wait:.0f}s...")
                    await asyncio.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator

import time
from typing import List

import gspread
from loguru import logger

from config import settings
from models.post import Post
from utils.helpers import retry


def load_existing_post_ids(ws: gspread.Worksheet) -> set[str]:
    """Read all values in the post_url column (G) and return as a set of post_ids."""
    from utils.helpers import extract_post_id
    try:
        urls = ws.col_values(settings.POST_URL_COLUMN_INDEX)
        ids = {extract_post_id(u) for u in urls if u and u != "post_url"}
        logger.info(f"Loaded {len(ids)} existing post IDs from sheet")
        return ids
    except gspread.exceptions.APIError as e:
        logger.error(f"Failed to read existing post IDs: {e}")
        return set()


@retry(max_attempts=3, delay=5.0, backoff=2.0)
def append_posts(ws: gspread.Worksheet, posts: List[Post]) -> int:
    """Deduplicate and batch-append new posts to the worksheet. Returns count added."""
    from utils.helpers import extract_post_id

    existing_ids = load_existing_post_ids(ws)
    new_posts = [p for p in posts if extract_post_id(p.post_url) not in existing_ids]

    if not new_posts:
        logger.info("No new posts to append")
        return 0

    rows = [p.to_row() for p in new_posts]
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    logger.info(f"Appended {len(new_posts)} new posts ({len(posts) - len(new_posts)} skipped as duplicates)")
    return len(new_posts)

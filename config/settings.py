import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

FB_EMAIL: str = os.environ["FB_EMAIL"]
FB_PASSWORD: str = os.environ["FB_PASSWORD"]
GROUP_URLS: list[str] = [u.strip() for u in os.environ["GROUP_URLS"].split(",") if u.strip()]

SHEET_ID: str = os.environ["SHEET_ID"]
WORKSHEET_NAME: str = os.getenv("WORKSHEET_NAME", "Posts")
SERVICE_ACCOUNT_JSON: Path = Path(os.getenv("SERVICE_ACCOUNT_JSON", "./config/service_account.json"))

COOKIE_PATH: Path = Path(os.getenv("COOKIE_PATH", "./cookies/fb_session.json"))
COOKIE_MAX_AGE_DAYS: int = int(os.getenv("COOKIE_MAX_AGE_DAYS", "7"))

MAX_SCROLLS: int = int(os.getenv("MAX_SCROLLS", "20"))
SCROLL_PAUSE_MIN_MS: int = int(os.getenv("SCROLL_PAUSE_MIN_MS", "2000"))
SCROLL_PAUSE_MAX_MS: int = int(os.getenv("SCROLL_PAUSE_MAX_MS", "5000"))

RUN_TIME: str = os.getenv("RUN_TIME", "08:00")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# HEADLESS=true  → chạy headless (cần xvfb-run nếu false trên server không có display)
# BROWSER_CHANNEL → để trống dùng Playwright bundled Chromium; hoặc "chrome" nếu cài Google Chrome
HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
BROWSER_CHANNEL: str | None = os.getenv("BROWSER_CHANNEL") or None

SHEET_HEADER = ["scraped_at", "author", "date", "text", "image_urls", "video_urls", "post_url"]
POST_URL_COLUMN_INDEX = 7  # column G (1-based)

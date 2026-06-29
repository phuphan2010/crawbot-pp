import random
from pathlib import Path
from datetime import datetime

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


# Realistic Chrome user-agent (update if needed)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
]


class BrowserManager:
    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self, headless: bool = False) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            channel="chrome",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
            ],
        )
        logger.info(f"Browser launched (headless={headless})")

    async def new_context(self, cookie_path: Path | None = None) -> BrowserContext:
        viewport = random.choice(VIEWPORTS)
        kwargs = dict(
            user_agent=USER_AGENT,
            viewport=viewport,
            locale="en-US",
            timezone_id="America/New_York",
        )
        if cookie_path and cookie_path.exists():
            kwargs["storage_state"] = str(cookie_path)
            logger.info(f"Injecting session from {cookie_path}")

        ctx = await self._browser.new_context(**kwargs)

        # Remove webdriver property
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        return ctx

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")


async def save_debug_screenshot(page: Page, label: str) -> None:
    debug_dir = Path("logs/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = debug_dir / f"{ts}_{label}.png"
    await page.screenshot(path=str(path), full_page=False)
    logger.warning(f"Debug screenshot saved: {path}")

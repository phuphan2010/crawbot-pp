"""
Development scheduler — keeps process alive and runs run_once daily at RUN_TIME.
For production on Windows, use Task Scheduler instead (see README).
Usage: python scheduler.py
"""
import asyncio
import time

import schedule
from loguru import logger

from config import settings
from utils.logger import setup_logger


def run_job():
    import run_once
    exit_code = asyncio.run(run_once.main())
    if exit_code != 0:
        logger.error(f"run_once exited with code {exit_code}")


if __name__ == "__main__":
    setup_logger(settings.LOG_LEVEL)
    logger.info(f"Scheduler started. Daily job at {settings.RUN_TIME}.")

    schedule.every().day.at(settings.RUN_TIME).do(run_job)

    # Run immediately on first start so you can verify it works
    logger.info("Running job immediately on startup...")
    run_job()

    while True:
        schedule.run_pending()
        time.sleep(60)

from pathlib import Path

import gspread
from loguru import logger

from auth.google_auth import get_gspread_client
from config import settings


def open_worksheet(service_account_json: Path, sheet_id: str, worksheet_name: str) -> gspread.Worksheet:
    client = get_gspread_client(service_account_json)
    spreadsheet = client.open_by_key(sheet_id)

    try:
        ws = spreadsheet.worksheet(worksheet_name)
        logger.info(f"Opened worksheet '{worksheet_name}'")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(settings.SHEET_HEADER))
        ws.append_row(settings.SHEET_HEADER)
        logger.info(f"Created worksheet '{worksheet_name}' with header")

    return ws

from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def get_gspread_client(service_account_json: Path) -> gspread.Client:
    creds = Credentials.from_service_account_file(str(service_account_json), scopes=SCOPES)
    return gspread.authorize(creds)

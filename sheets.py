"""Чтение постов из Google Sheets."""

import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from config import Config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DATE_FORMATS = ["%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S"]


def _parse_date_str(dt_str: str) -> datetime | None:
    """Попробовать распарсить строку даты в одном из допустимых форматов."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    return None


def get_gspread_client(config: Config) -> gspread.Client:
    """Создать авторизованный gspread-клиент через service account."""
    creds = Credentials.from_service_account_file(config.GOOGLE_CREDENTIALS_JSON, scopes=SCOPES)
    return gspread.authorize(creds)


def get_posts_from_sheet(config: Config) -> list[dict]:
    """Прочитать валидные посты (текст + дата) из Google Sheets начиная со строки 2."""
    client = get_gspread_client(config)
    spreadsheet = client.open_by_key(config.SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(config.SHEET_NAME)

    all_rows = worksheet.get_all_values()
    posts: list[dict] = []

    # Строка 0 — заголовок, начинаем с индекса 1 (строка 2 в таблице)
    for idx, row in enumerate(all_rows[1:], start=2):
        text = row[0].strip() if len(row) > 0 else ""
        dt_str = row[1].strip() if len(row) > 1 else ""

        if not text or not dt_str:
            logger.warning("Строка %d: пустое поле A или B — пропущена", idx)
            continue

        parsed = _parse_date_str(dt_str)
        if parsed is None:
            logger.warning(
                "Строка %d: не удалось распарсить дату '%s' — пропущена", idx, dt_str
            )
            continue

        posts.append({"row": idx, "text": text, "dt_str": dt_str})

    return posts

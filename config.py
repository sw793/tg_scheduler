"""Загрузка и валидация конфигурации из .env."""

from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str
    API_ID: int
    API_HASH: str
    SESSION_STRING: str
    CHANNEL_ID: int
    ADMIN_ID: int
    GOOGLE_CREDENTIALS_JSON: str
    SPREADSHEET_ID: str
    SHEET_NAME: str
    TIMEZONE: str
    EXPORT_TARGET: str  # "sheets" | "xlsx"


def load_config() -> Config:
    """Загрузить конфигурацию из переменных окружения с валидацией обязательных полей."""
    required_str = [
        "BOT_TOKEN",
        "API_HASH",
        "SESSION_STRING",
        "GOOGLE_CREDENTIALS_JSON",
        "SPREADSHEET_ID",
    ]
    for key in required_str:
        if not os.getenv(key):
            raise ValueError(f"Обязательная переменная окружения не задана: {key}")

    for key in ["API_ID", "CHANNEL_ID", "ADMIN_ID"]:
        val = os.getenv(key)
        if not val:
            raise ValueError(f"Обязательная переменная окружения не задана: {key}")
        try:
            int(val)
        except ValueError:
            raise ValueError(f"{key} должен быть целым числом, получено: '{val}'")

    export_target = os.getenv("EXPORT_TARGET", "sheets")
    if export_target not in ("sheets", "xlsx"):
        raise ValueError(f"EXPORT_TARGET должен быть 'sheets' или 'xlsx', получено: '{export_target}'")

    return Config(
        BOT_TOKEN=os.getenv("BOT_TOKEN"),
        API_ID=int(os.getenv("API_ID")),
        API_HASH=os.getenv("API_HASH"),
        SESSION_STRING=os.getenv("SESSION_STRING"),
        CHANNEL_ID=int(os.getenv("CHANNEL_ID")),
        ADMIN_ID=int(os.getenv("ADMIN_ID")),
        GOOGLE_CREDENTIALS_JSON=os.getenv("GOOGLE_CREDENTIALS_JSON"),
        SPREADSHEET_ID=os.getenv("SPREADSHEET_ID"),
        SHEET_NAME=os.getenv("SHEET_NAME", "Sheet1"),
        TIMEZONE=os.getenv("TIMEZONE", "Europe/Moscow"),
        EXPORT_TARGET=export_target,
    )

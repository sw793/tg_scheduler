"""Точка входа: запуск aiogram-бота и Pyrogram-клиента параллельно."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from pyrogram import Client as PyrogramClient

from bot.handlers import setup_handlers
from bot.middleware import SingleAdminMiddleware
from config import load_config
from sheets import get_gspread_client


def setup_logging() -> None:
    """Настроить логирование: INFO в файл, WARNING в консоль."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt))

    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])


async def main() -> None:
    """Инициализировать и запустить бота и Pyrogram-клиент."""
    setup_logging()
    logger = logging.getLogger(__name__)

    config = load_config()

    # Проверка подключения к Google Sheets при старте
    try:
        get_gspread_client(config)
        logger.info("Google Sheets API: подключение успешно")
    except Exception as exc:
        logger.error("Google Sheets API: ошибка подключения: %s", exc)

    # Pyrogram MTProto-клиент
    pyrogram_client = PyrogramClient(
        name="scheduled_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=config.SESSION_STRING,
    )

    # aiogram Bot + Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.middleware(SingleAdminMiddleware(config))

    setup_handlers(dp, bot, pyrogram_client, config)

    logger.info("Запуск бота...")

    await pyrogram_client.start()
    logger.info("Pyrogram MTProto клиент запущен")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await pyrogram_client.stop()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())

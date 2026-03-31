"""Обработчики команд aiogram-бота."""

import logging
import traceback
from io import BytesIO
from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

import scheduler
import sheets
from config import Config

if TYPE_CHECKING:
    from pyrogram import Client

logger = logging.getLogger(__name__)
router = Router()

# Хранилище pending ids для /confirm_delete: {admin_id: [message_id, ...]}
_pending_delete: dict[int, list[int]] = {}


def setup_handlers(dp: Dispatcher, bot: Bot, pyrogram_client: "Client", config: Config) -> None:
    """Зарегистрировать роутер и передать зависимости через data."""
    dp.include_router(router)
    dp.update.middleware.register  # уже подключён в main.py
    # Передаём зависимости через workflow_data диспетчера
    dp["pyrogram_client"] = pyrogram_client
    dp["config"] = config
    dp["bot"] = bot


# ─────────────────────────────── /start /help ────────────────────────────────

@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    """Показать справку по командам."""
    text = (
        "📋 <b>Команды бота</b>\n\n"
        "/import — загрузить посты из Google Sheets и запланировать\n"
        "/export — экспортировать запланированные посты (в Sheets или .xlsx)\n"
        "/status — показать количество и ближайший запланированный пост\n"
        "/delete_scheduled — удалить посты по ID\n"
        "  • Прикрепите .xlsx или .csv файл с ID\n"
        "  • Или укажите ID в теле сообщения (по одному на строку)\n"
        "/confirm_delete — подтвердить удаление после /delete_scheduled\n"
    )
    await message.answer(text, parse_mode="HTML")


# ─────────────────────────────── /import ─────────────────────────────────────

@router.message(Command("import"))
async def cmd_import(
    message: Message,
    pyrogram_client: "Client",
    config: Config,
) -> None:
    """Прочитать посты из Google Sheets и запланировать их через Pyrogram."""
    try:
        posts = sheets.get_posts_from_sheet(config)
    except Exception as exc:
        logger.error("Ошибка чтения Google Sheets: %s", traceback.format_exc())
        await message.answer(f"Ошибка доступа к Google Sheets: {type(exc).__name__}")
        return

    if not posts:
        await message.answer("Нет валидных строк в таблице")
        return

    await message.answer(f"Загружаю {len(posts)} постов...")

    try:
        result = await scheduler.import_posts(pyrogram_client, posts, config)
    except Exception as exc:
        logger.error("Ошибка импорта постов: %s", traceback.format_exc())
        await message.answer(f"Ошибка: {type(exc).__name__}. Подробности в bot.log")
        return

    success_count = len(result["success"])
    skipped = result["skipped"]
    failed = result["failed"]

    lines = [f"✅ Загружено: {success_count}"]
    lines.append(f"⏭ Пропущено: {len(skipped)}")

    if skipped:
        lines.append("\nПропущенные строки:")
        for s in skipped:
            lines.append(f"  • Строка {s['row']}: {s['reason']}")

    if failed:
        lines.append(f"\n❌ Ошибок: {len(failed)}")
        for f_ in failed:
            lines.append(f"  • Строка {f_['row']}: {f_['error']}")

    await message.answer("\n".join(lines))


# ─────────────────────────────── /export ─────────────────────────────────────

@router.message(Command("export"))
async def cmd_export(
    message: Message,
    pyrogram_client: "Client",
    config: Config,
    bot: Bot,
) -> None:
    """Экспортировать запланированные посты в Google Sheets или .xlsx."""
    try:
        posts = await scheduler.export_scheduled(pyrogram_client, config)
    except Exception as exc:
        logger.error("Ошибка экспорта: %s", traceback.format_exc())
        await message.answer(f"Ошибка: {type(exc).__name__}. Подробности в bot.log")
        return

    if not posts:
        await message.answer("Нет запланированных постов")
        return

    if config.EXPORT_TARGET == "sheets":
        try:
            url = scheduler.write_export_to_sheets(posts, config)
        except Exception as exc:
            logger.error("Ошибка записи в Sheets: %s", traceback.format_exc())
            await message.answer(f"Ошибка доступа к Google Sheets: {type(exc).__name__}")
            return
        await message.answer(
            f"✅ Экспортировано {len(posts)} постов.\n"
            f"🔗 {url}\n\n"
            "Удалите из листа строки, которые НЕ нужно удалять, "
            "затем отправьте файл боту командой /delete_scheduled и прикрепите файл."
        )
    else:
        try:
            xlsx_bytes = scheduler.write_export_to_xlsx(posts)
        except Exception as exc:
            logger.error("Ошибка создания xlsx: %s", traceback.format_exc())
            await message.answer(f"Ошибка: {type(exc).__name__}. Подробности в bot.log")
            return

        file = BufferedInputFile(xlsx_bytes, filename="scheduled_posts.xlsx")
        await bot.send_document(
            message.chat.id,
            document=file,
            caption=(
                f"✅ Экспортировано {len(posts)} постов.\n\n"
                "Удалите из файла строки, которые НЕ нужно удалять, "
                "затем отправьте файл боту командой /delete_scheduled и прикрепите файл."
            ),
        )


# ─────────────────────────────── /status ─────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(
    message: Message,
    pyrogram_client: "Client",
    config: Config,
) -> None:
    """Показать количество запланированных постов и ближайший."""
    try:
        posts = await scheduler.export_scheduled(pyrogram_client, config)
    except Exception as exc:
        logger.error("Ошибка получения статуса: %s", traceback.format_exc())
        await message.answer(f"Ошибка: {type(exc).__name__}. Подробности в bot.log")
        return

    if not posts:
        await message.answer("Запланированных постов: 0")
        return

    nearest = posts[0]["date"]  # уже отсортированы по возрастанию
    await message.answer(
        f"📊 Запланированных постов: {len(posts)}\n"
        f"⏰ Ближайший: {nearest}"
    )


# ─────────────────────────────── /delete_scheduled ───────────────────────────

@router.message(Command("delete_scheduled"))
async def cmd_delete_scheduled(
    message: Message,
    pyrogram_client: "Client",
    config: Config,
    bot: Bot,
) -> None:
    """Принять список ID на удаление из файла или текста и запросить подтверждение."""
    ids: list[int] = []

    # Режим A — прикреплён файл
    if message.document:
        filename = message.document.file_name or ""
        if filename.endswith(".xlsx"):
            fmt = "xlsx"
        elif filename.endswith(".csv"):
            fmt = "csv"
        else:
            await message.answer("Поддерживаются только .xlsx и .csv файлы")
            return

        try:
            file_bytes_io = BytesIO()
            await bot.download(message.document, destination=file_bytes_io)
            raw = file_bytes_io.getvalue()
            ids = scheduler.parse_ids_from_input(raw, fmt)
        except Exception as exc:
            logger.error("Ошибка парсинга файла: %s", traceback.format_exc())
            await message.answer(f"Ошибка обработки файла: {type(exc).__name__}")
            return

    else:
        # Режим B — текст после команды
        text_after_cmd = message.text or ""
        # Убрать саму команду (/delete_scheduled ...)
        parts = text_after_cmd.split(maxsplit=1)
        body = parts[1].strip() if len(parts) > 1 else ""

        if not body:
            await message.answer(
                "Укажите ID постов (по одному на строку) после команды "
                "или прикрепите .xlsx/.csv файл."
            )
            return

        try:
            ids = scheduler.parse_ids_from_input(body, "text")
        except Exception as exc:
            logger.error("Ошибка парсинга текста: %s", traceback.format_exc())
            await message.answer(f"Ошибка обработки текста: {type(exc).__name__}")
            return

    if not ids:
        await message.answer("Не найдено ни одного валидного message_id")
        return

    _pending_delete[config.ADMIN_ID] = ids
    await message.answer(
        f"⚠️ Будут удалены {len(ids)} постов.\n"
        "Подтвердите: /confirm_delete"
    )


# ─────────────────────────────── /confirm_delete ─────────────────────────────

@router.message(Command("confirm_delete"))
async def cmd_confirm_delete(
    message: Message,
    pyrogram_client: "Client",
    config: Config,
) -> None:
    """Выполнить удаление запланированных постов после подтверждения."""
    ids = _pending_delete.get(config.ADMIN_ID)
    if not ids:
        await message.answer("Нет ожидающих удаления постов. Сначала используйте /delete_scheduled")
        return

    try:
        result = await scheduler.delete_scheduled_posts(pyrogram_client, ids, config)
    except Exception as exc:
        logger.error("Ошибка удаления: %s", traceback.format_exc())
        await message.answer(f"Ошибка: {type(exc).__name__}. Подробности в bot.log")
        return
    finally:
        _pending_delete.pop(config.ADMIN_ID, None)

    not_found_count = len(result["not_found"])
    await message.answer(
        f"✅ Удалено: {result['deleted']}\n"
        f"❓ Не найдено: {not_found_count}"
        + (" (возможно уже опубликованы)" if not_found_count else "")
    )

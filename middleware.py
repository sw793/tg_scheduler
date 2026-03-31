"""Middleware: пропускать только сообщения от единственного администратора."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from config import Config

logger = logging.getLogger(__name__)


class SingleAdminMiddleware(BaseMiddleware):
    """Молча игнорировать все апдейты не от ADMIN_ID."""

    def __init__(self, config: Config) -> None:
        """Инициализировать middleware с конфигурацией."""
        self.admin_id = config.ADMIN_ID
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Проверить user_id и либо передать управление дальше, либо проигнорировать."""
        user = data.get("event_from_user")
        if user is None and isinstance(event, Message):
            user = event.from_user

        if user is None or user.id != self.admin_id:
            logger.debug("Игнорирован апдейт от user_id=%s", user.id if user else "unknown")
            return None

        return await handler(event, data)

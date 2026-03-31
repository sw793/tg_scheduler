"""Одноразовый скрипт для генерации Pyrogram SESSION_STRING. Запускать вручную в терминале."""

import asyncio
from pyrogram import Client
from dotenv import load_dotenv
import os

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")


async def main() -> None:
    """Авторизоваться через MTProto и напечатать SESSION_STRING."""
    if not API_ID or not API_HASH:
        raise ValueError("API_ID и API_HASH должны быть заполнены в .env перед запуском")

    async with Client(
        name="session_gen",
        api_id=API_ID,
        api_hash=API_HASH,
        in_memory=True,
    ) as client:
        session_string = await client.export_session_string()
        print("\n" + "=" * 60)
        print("SESSION_STRING (скопируйте в .env):")
        print("=" * 60)
        print(session_string)
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

"""
Telegram Video Downloader Bot — entry point.
Run:  python bot.py
Env:  BOT_TOKEN=<your token>
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import BOT_TOKEN
from handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN is not set.\n"
            "• Local: create a .env file with BOT_TOKEN=your_token\n"
            "• Railway: add BOT_TOKEN in the Variables tab"
        )

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # allowed_updates включает message для личных чатов И групп
    logger.info("Bot is starting…")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message"],
        )
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")

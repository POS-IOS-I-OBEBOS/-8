import asyncio
import logging
from aiogram import Bot, Dispatcher

from kitchen_gen_bot.bot.handlers import router


logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    token = input("Enter bot token: ")
    logger.info("Token received")
    bot = Bot(token)
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Starting polling")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
    logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())

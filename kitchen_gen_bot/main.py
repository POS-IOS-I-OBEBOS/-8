import asyncio
from aiogram import Bot, Dispatcher

from bot.handlers import router


async def main():
    token = input("Enter bot token: ")
    bot = Bot(token)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

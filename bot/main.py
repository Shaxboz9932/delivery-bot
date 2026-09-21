import os
import sys
import asyncio
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Handlerlarni import qilamiz
from bot.handlers import restaurant, courier, customer

BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Routerlarni ulash
    # main.py ichida
    dp.include_router(courier.router)  # Courier birinchi ulansin
    dp.include_router(restaurant.router)
    dp.include_router(customer.router)  # Customer oxirida bo'ladi

    print("Bot muvaffaqiyatli ishga tushdi va handlerlar ulandi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
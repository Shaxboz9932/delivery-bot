import os
import sys
import asyncio
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
import logging

# Loggerni sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_errors.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Handlerlarni import qilamiz
from bot.handlers import restaurant, courier, customer

BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Redis ulanishi (FSM va Throttling uchun)
    # Eslatma: Docker'da Redis porti 6379 ga map qilingan bo'lishi kerak
    redis_client = Redis(host='localhost', port=6379, db=0)
    storage = RedisStorage(redis=redis_client)
    
    dp = Dispatcher(storage=storage)

    # Throttling (Anti-Spam) middleware ni ulaymiz
    from bot.middlewares.throttling import ThrottlingMiddleware
    dp.message.middleware(ThrottlingMiddleware(redis=redis_client, rate_limit=1.0))
    dp.callback_query.middleware(ThrottlingMiddleware(redis=redis_client, rate_limit=1.0))

    # Routerlarni ulash
    # main.py ichida
    dp.include_router(courier.router)  # Courier birinchi ulansin
    dp.include_router(restaurant.router)
    dp.include_router(customer.router)  # Customer oxirida bo'ladi

    # Global error handler
    @dp.errors()
    async def global_error_handler(event: types.ErrorEvent):
        logger.exception(f"Kutilmagan xatolik yuz berdi: {event.exception}")

    # Menyu komandalarini o'rnatish
    async def set_default_commands(bot: Bot):
        commands = [
            types.BotCommand(command="start", description="Botni ishga tushirish"),
            types.BotCommand(command="myorders", description="Mening buyurtmalarim"),
            types.BotCommand(command="balance", description="Kuryerlar uchun balans")
        ]
        await bot.set_my_commands(commands)
    
    await set_default_commands(bot)

    logger.info("Bot muvaffaqiyatli ishga tushdi va handlerlar ulandi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
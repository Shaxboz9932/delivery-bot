import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from redis.asyncio import Redis

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, rate_limit: float = 1.0):
        self.redis = redis
        self.rate_limit = rate_limit

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        
        # Faqat Message va CallbackQuery larni cheklaymiz
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
            
        user_id = event.from_user.id
        
        # Redisdan foydalanuvchining oxirgi harakat vaqtini olamiz
        last_action = await self.redis.get(f"throttle_{user_id}")
        current_time = time.time()
        
        if last_action:
            last_action_time = float(last_action)
            # Agar rate_limit vaqtidan oldin yana so'rov kelgan bo'lsa
            if current_time - last_action_time < self.rate_limit:
                if isinstance(event, Message):
                    await event.answer("⚠️ Iltimos, tugmalarni sekinroq bosing!")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Iltimos, tugmalarni sekinroq bosing!", show_alert=True)
                # So'rovni shu yerda to'xtatamiz (handlerga bormaydi)
                return
                
        # Yangi vaqtni Redisga saqlaymiz va 2 soniyadan keyin avtomatik o'chishini tayinlaymiz
        await self.redis.set(f"throttle_{user_id}", str(current_time), ex=2)
        
        return await handler(event, data)

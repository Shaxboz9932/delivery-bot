from aiogram import Router, types
from aiogram.filters import Command

router = Router()

# Kuryerlar guruhi ID'sini shu yerga bir marta yozib qo'yasiz
COURIER_GROUP_ID = -1004456884189

# Guruh ID larini bilish uchun yordamchi message handler
@router.message(Command("chat_id"))
async def get_chat_id(message: types.Message):
    print(f"Ushbu guruh CHAT_ID si: {message.chat.id}")
    await message.answer(f"Ushbu chat ID si: {message.chat.id}")

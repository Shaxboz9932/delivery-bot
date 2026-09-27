from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from orders.models import Restaurant

router = Router()

# 1. /start bosilganda asosiy menyu
@router.message(CommandStart())
async def start_handler(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🛒 Zakaz berish"))
    builder.add(types.KeyboardButton(text="🛒 Savatni ko'rish"))
    builder.add(types.KeyboardButton(text="📜 Mening buyurtmalarim"))
    builder.adjust(2)

    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\n"
        f"Kerakli bo'limni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# 2. "Zakaz berish" bosilganda Restoranlarni chiqarish
@router.message(F.text == "🛒 Zakaz berish")
async def show_restaurants(message: types.Message):
    restaurants = [r async for r in Restaurant.objects.filter(is_active=True)]

    if not restaurants:
        await message.answer("Hozircha xizmat ko'rsatadigan restoranlar mavjud emas.")
        return

    builder = InlineKeyboardBuilder()
    for rest in restaurants:
        # Ish vaqti ko'rsatilgan bo'lsa — ochiq/yopiq belgisini qo'shamiz
        if rest.opening_time and rest.closing_time:
            status = "🟢" if rest.is_open() else "🔴"
            work_hours = f"{rest.opening_time.strftime('%H:%M')}–{rest.closing_time.strftime('%H:%M')}"
            label = f"{status} {rest.name} ({work_hours})"
        else:
            label = f"🍽 {rest.name}"

        builder.add(types.InlineKeyboardButton(
            text=label,
            callback_data=f"rest_{rest.id}"
        ))
    builder.adjust(1)

    await message.answer(
        "O'zingizga ma'qul restoranni tanlang:",
        reply_markup=builder.as_markup()
    )

# 5. Restoranlar ro'yxatiga qaytish (Back Button)
@router.callback_query(F.data == "back_to_restaurants")
async def back_to_restaurants_handler(callback: types.CallbackQuery):
    restaurants = [r async for r in Restaurant.objects.filter(is_active=True)]

    builder = InlineKeyboardBuilder()
    for rest in restaurants:
        builder.add(types.InlineKeyboardButton(
            text=f"🍽 {rest.name}",
            callback_data=f"rest_{rest.id}"
        ))
    builder.adjust(2)

    await callback.message.edit_text(
        "O'zingizga ma'qul restoranni tanlang:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

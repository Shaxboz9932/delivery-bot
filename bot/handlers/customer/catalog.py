import os
import math
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from django.conf import settings

from orders.models import Restaurant, Category, MenuItem

router = Router()

# 3. Restoran tanlanganda uning Kategoriyalarini chiqarish
@router.callback_query(F.data.startswith("rest_"))
async def show_categories(callback: types.CallbackQuery, state: FSMContext, bot):
    rest_id = int(callback.data.split("_")[1])

    try:
        restaurant = await Restaurant.objects.aget(id=rest_id, is_active=True)
    except Restaurant.DoesNotExist:
        await callback.answer("Restoran topilmadi!", show_alert=True)
        return

    # Ish vaqti tekshiruvi
    if not restaurant.is_open():
        open_t = restaurant.opening_time.strftime('%H:%M') if restaurant.opening_time else "?"
        close_t = restaurant.closing_time.strftime('%H:%M') if restaurant.closing_time else "?"
        await callback.answer(
            f"🔴 Kafe ish vaqti tugagan!\n"
            f"Ish vaqti: {open_t} – {close_t}",
            show_alert=True
        )
        return

    categories = [c async for c in Category.objects.filter(restaurant=restaurant)]

    if not categories:
        await callback.answer("Ushbu restoranda hozircha kategoriyalar yo'q.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.add(types.InlineKeyboardButton(
            text=f"📁 {cat.name}",
            callback_data=f"cat_{cat.id}"
        ))

    builder.add(types.InlineKeyboardButton(text="⬅️ Restoranlarga qaytish", callback_data="back_to_restaurants"))
    builder.adjust(1)

    # Oldingi taomlar menyusini (agar bo'lsa) tozalash
    state_data = await state.get_data()
    old_msg_ids = state_data.get("menu_msg_ids", [])
    if old_msg_ids:
        for msg_id in old_msg_ids:
            if msg_id != callback.message.message_id:
                try:
                    await bot.delete_message(chat_id=callback.from_user.id, message_id=msg_id)
                except:
                    pass
        await state.update_data(menu_msg_ids=[])

    text = f"<b>{restaurant.name}</b> bo'limini tanlang:"
    if restaurant.phone_number:
        text += f"\n📞 Aloqa uchun: {restaurant.phone_number}"

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# 4. Kategoriya tanlanganda unga tegishli Taomlarni (MenuItem) chiqarish
@router.callback_query(F.data.startswith("cat_") | F.data.startswith("page_"))
async def show_menu_items(callback: types.CallbackQuery, state: FSMContext, bot):
    data = callback.data
    if data.startswith("cat_"):
        cat_id = int(data.split("_")[1])
        page = 1
    else:
        parts = data.split("_")
        cat_id = int(parts[1])
        page = int(parts[2])

    try:
        category = await Category.objects.select_related('restaurant').aget(id=cat_id)
    except Category.DoesNotExist:
        await callback.answer("Kategoriya topilmadi!", show_alert=True)
        return

    items = [item async for item in MenuItem.objects.prefetch_related('images').filter(category=category, is_active=True)]

    if not items:
        await callback.answer("Ushbu bo'limda hozircha taomlar yo'q.", show_alert=True)
        return

    per_page = 3
    total_items = len(items)
    total_pages = math.ceil(total_items / per_page)
    
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = items[start_idx:end_idx]

    # Oldingi xabarlarni tozalash (eski sahifadagi taomlarni o'chirish)
    state_data = await state.get_data()
    old_msg_ids = state_data.get("menu_msg_ids", [])
    
    if callback.message.message_id not in old_msg_ids:
        try:
            await callback.message.delete()
        except:
            pass

    for msg_id in old_msg_ids:
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=msg_id)
        except:
            pass

    new_msg_ids = []

    header_msg = await bot.send_message(
        chat_id=callback.from_user.id,
        text=f"<b>{category.restaurant.name} ➔ {category.name}:</b>\n<i>Sahifa: {page}/{total_pages} | Kerakli taomlarni savatga qo'shing.</i>"
    )
    new_msg_ids.append(header_msg.message_id)

    for item in page_items:
        price_val = float(item.price)
        formatted_price = f"{price_val:,.0f}".replace(",", " ") if price_val.is_integer() else f"{price_val:,.2f}".replace(",", " ")

        caption = f"<b>{item.name}</b> — {formatted_price} so'm"
        if item.description:
            caption += f"\n\n<i>{item.description}</i>"

        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text=f"➕ Savatga qo'shish ({formatted_price} so'm)",
            callback_data=f"add_to_cart_{item.id}"
        ))
        cart_markup = builder.as_markup()

        # Barcha rasmlarni yuklaymiz
        images = [img async for img in item.images.all()]

        # Mavjud rasm fayllarini filtrlaymiz
        valid_paths = []
        for img in images:
            full_path = os.path.join(settings.MEDIA_ROOT, img.image.name)
            if os.path.exists(full_path):
                valid_paths.append((full_path, img.is_main))

        # Asosiy rasmni birinchi qilib tartiblash
        valid_paths.sort(key=lambda x: (not x[1]))  # is_main=True birinchi

        if len(valid_paths) == 0:
            msg = await bot.send_message(
                chat_id=callback.from_user.id,
                text=caption,
                reply_markup=cart_markup
            )
            new_msg_ids.append(msg.message_id)

        elif len(valid_paths) == 1:
            photo = FSInputFile(valid_paths[0][0])
            msg = await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=photo,
                caption=caption,
                reply_markup=cart_markup
            )
            new_msg_ids.append(msg.message_id)

        else:
            media_group = []
            for idx, (path, _) in enumerate(valid_paths[:10]):  # Telegram max 10
                photo = FSInputFile(path)
                if idx == 0:
                    media_group.append(types.InputMediaPhoto(media=photo, caption=caption))
                else:
                    media_group.append(types.InputMediaPhoto(media=photo))

            msgs = await bot.send_media_group(
                chat_id=callback.from_user.id,
                media=media_group
            )
            for m in msgs:
                new_msg_ids.append(m.message_id)
                
            msg2 = await bot.send_message(
                chat_id=callback.from_user.id,
                text=f"⬆️ <b>{item.name}</b> uchun:",
                reply_markup=cart_markup
            )
            new_msg_ids.append(msg2.message_id)

    # Orqaga qaytish va navigatsiya tugmasi
    back_builder = InlineKeyboardBuilder()
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"page_{cat_id}_{page-1}"))
    if page < total_pages:
        nav_buttons.append(types.InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"page_{cat_id}_{page+1}"))
        
    if nav_buttons:
        back_builder.row(*nav_buttons)

    back_builder.row(types.InlineKeyboardButton(
        text="⬅️ Kategoriyalarga qaytish",
        callback_data=f"rest_{category.restaurant.id}"
    ))

    nav_msg = await bot.send_message(
        chat_id=callback.from_user.id,
        text="Boshqa bo'limlarni ham ko'rish uchun:",
        reply_markup=back_builder.as_markup()
    )
    new_msg_ids.append(nav_msg.message_id)
    
    await state.update_data(menu_msg_ids=new_msg_ids)
    await callback.answer()

import os
import uuid
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from django.conf import settings

from orders.models import Restaurant, Order, OrderStatus, OrderItem
from .states import OrderCheckout

router = Router()

# 11. "Buyurtmani rasmiylashtirish" (Checkout) bosilganda
@router.callback_query(F.data == "checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await callback.answer("Savatingiz bo'sh!", show_alert=True)
        return

    await callback.message.delete()  # Inline xabarni o'chiramiz
    
    zone_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏙 Shahar ichi (10 000 so'm)", callback_data="zone_inside")],
        [types.InlineKeyboardButton(text="🛣 Shahar tashqarisi (15 000 so'm)", callback_data="zone_outside")]
    ])

    await callback.message.answer(
        "📍 <b>Yetkazib berish hududini tanlang:</b>",
        reply_markup=zone_keyboard
    )

    await state.set_state(OrderCheckout.waiting_for_delivery_zone)
    await callback.answer()

@router.callback_query(OrderCheckout.waiting_for_delivery_zone, F.data.startswith("zone_"))
async def process_delivery_zone(callback: types.CallbackQuery, state: FSMContext):
    zone = callback.data.split("_")[1]
    delivery_price = 10000.0 if zone == "inside" else 15000.0
    
    await state.update_data(delivery_price=delivery_price)
    
    await callback.message.delete()
    await callback.message.answer(
        "Ajoyib! Endi <b>to'liq yetkazib berish manzilini</b> qo'lda yozib yuboring:\n"
        "<i>(Masalan: Markaziy ko'cha, 12-uy, 4-xonadon / Mo'ljal: Maktab yonida)</i>",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await state.set_state(OrderCheckout.waiting_for_location)
    await callback.answer()


# 12. Manzil qabul qilinganda va Telefon so'rash
@router.message(OrderCheckout.waiting_for_location)
async def process_location(message: types.Message, state: FSMContext, bot):
    await state.update_data(location_text=message.text)

    # Telefon raqam so'rash uchun Keyboard Button
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True))

    await message.answer(
        "Rahmat! Aloqa uchun <b>telefon raqamingizni</b> yuboring:",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )
    await state.set_state(OrderCheckout.waiting_for_phone)


# 13. Telefon raqam qabul qilish va To'lov turini so'rash
@router.message(OrderCheckout.waiting_for_phone, F.content_type.in_({'contact', 'text'}))
async def process_phone(message: types.Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text

    await state.update_data(phone_number=phone)

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Yetkazilganda (Naqd pul)", callback_data="pay_cash"))
    builder.row(types.InlineKeyboardButton(text="Yetkazilganda (Karta/Click orqali)", callback_data="pay_card_delivery"))
    builder.row(types.InlineKeyboardButton(text="Karta orqali hoziroq to'lash", callback_data="pay_card_now"))

    data = await state.get_data()
    delivery_price = data.get("delivery_price", 10000.0)
    fmt_delivery = f"{delivery_price:,.0f}".replace(",", " ")

    await message.answer(
        f"<b>Diqqat: Yetkazib berish xizmati narxi {fmt_delivery} so'm hisoblanadi.</b>\n\n"
        "To'lov turini tanlang:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OrderCheckout.waiting_for_payment_method)


# 14. To'lov turini qabul qilish va saqlash/So'rov
@router.callback_query(OrderCheckout.waiting_for_payment_method)
async def process_payment_method(callback: types.CallbackQuery, state: FSMContext, bot):
    payment_method = callback.data

    data = await state.get_data()
    cart = data.get("cart", {})
    restaurant_id = data.get("restaurant_id")

    try:
        restaurant = await Restaurant.objects.aget(id=restaurant_id)
    except Restaurant.DoesNotExist:
        await callback.answer("Restoran topilmadi!", show_alert=True)
        await state.clear()
        return

    DELIVERY_PRICE = data.get("delivery_price", 10000.0)

    total_price = 0.0
    for item_id, item in cart.items():
        total_price += float(item['price']) * item['quantity']

    total_price_with_delivery = total_price + DELIVERY_PRICE
    formatted_total = f"{total_price_with_delivery:,.0f}".replace(",", " ") if total_price_with_delivery.is_integer() else f"{total_price_with_delivery:,.2f}".replace(",", " ")

    if payment_method == "pay_cash":
        await state.update_data(payment_method="cash")
        await finalize_order(callback.message, state, bot, callback.from_user)
        await callback.message.delete()

    elif payment_method == "pay_card_delivery":
        await state.update_data(payment_method="card_delivery")
        await finalize_order(callback.message, state, bot, callback.from_user)
        await callback.message.delete()

    elif payment_method == "pay_card_now":
        await state.update_data(payment_method="card_now")

        card_info = f"<b>Karta raqami:</b> <code>{restaurant.card_number}</code>\n<b>Karta egasi:</b> {restaurant.card_owner_name}" if restaurant.card_number else "Karta ma'lumotlari kiritilmagan. Iltimos admin bilan bog'laning yoki Naqd to'lovni tanlang."

        await callback.message.edit_text(
            f"Siz karta orqali to'lovni tanladingiz.\n\n"
            f"Jami to'lov summasi: <b>{formatted_total} so'm</b>\n\n"
            f"{card_info}\n\n"
            f"Iltimos, to'lovni amalga oshirganingizdan so'ng <b>skrinshotni shu yerga yuboring.</b>"
        )
        await state.set_state(OrderCheckout.waiting_for_payment_screenshot)

    await callback.answer()


# 15. Mijoz to'lov skrinshotini yuborganda (Restoran tasdiqlaganidan so'ng)
@router.message(OrderCheckout.waiting_for_payment_screenshot, F.photo)
async def process_payment_screenshot(message: types.Message, state: FSMContext, bot):
    photo_id = message.photo[-1].file_id # Eng sifatli rasmni olamiz
    await state.update_data(payment_screenshot_url=photo_id)

    await finalize_order(message, state, bot, message.from_user)


async def finalize_order(message_or_callback_msg, state: FSMContext, bot, user):
    data = await state.get_data()
    cart = data.get("cart", {})
    restaurant_id = data.get("restaurant_id")
    phone = data.get("phone_number")
    address_text = data.get("location_text")
    payment_method = data.get("payment_method")
    payment_screenshot_url = data.get("payment_screenshot_url")

    try:
        restaurant = await Restaurant.objects.aget(id=restaurant_id)
    except Restaurant.DoesNotExist:
        await message_or_callback_msg.answer("Restoran topilmadi!", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    DELIVERY_PRICE = data.get("delivery_price", 10000.0)

    items_text = ""
    total_price = 0.0

    for item_id, item in cart.items():
        item_price = float(item['price'])
        item_total = item_price * item['quantity']
        total_price += item_total

        fmt_price = f"{item_price:,.0f}".replace(",", " ") if item_price.is_integer() else f"{item_price:,.2f}".replace(",", " ")
        fmt_total = f"{item_total:,.0f}".replace(",", " ") if item_total.is_integer() else f"{item_total:,.2f}".replace(",", " ")

        items_text += f"• <b>{item['name']}</b>: {item['quantity']} dona x {fmt_price} = {fmt_total} so'm\n"

    fmt_delivery = f"{DELIVERY_PRICE:,.0f}".replace(",", " ")
    items_text += f"\n🚚 Yetkazib berish xizmati: {fmt_delivery} so'm\n"

    total_price_with_delivery = total_price + DELIVERY_PRICE
    formatted_total = f"{total_price_with_delivery:,.0f}".replace(",", " ") if total_price_with_delivery.is_integer() else f"{total_price_with_delivery:,.2f}".replace(",", " ")

    payment_method_dict = {
        "cash": "Naqd (Yetkazib berilganda)",
        "card_delivery": "Karta orqali (Yetkazib berilganda)",
        "card_now": "Karta orqali hoziroq"
    }
    payment_text = payment_method_dict.get(payment_method, "Noma'lum")

    # 1. Bazada Order yaratamiz
    is_paid_now = payment_method == "card_now" and payment_screenshot_url is not None
    order = await Order.objects.acreate(
        customer_tg_id=user.id,
        restaurant=restaurant,
        total_price=total_price_with_delivery,
        address_text=f"Tel: {phone}\nManzil: {address_text}",
        status=OrderStatus.CREATED,
        payment_method=payment_method,
        payment_screenshot_url=payment_screenshot_url,
        is_paid=is_paid_now
    )

    # 1a. Har bir taom uchun OrderItem yozamiz
    for item_id, item in cart.items():
        await OrderItem.objects.acreate(
            order=order,
            item_name=item['name'],
            item_price=item['price'],
            quantity=item['quantity']
        )

    # 2. Restoran guruhiga inline klaviatura
    restaurant_keyboard = InlineKeyboardBuilder()
    restaurant_keyboard.add(types.InlineKeyboardButton(
        text="✅ Qabul qilish",
        callback_data=f"accept_order_{order.id}"
    ))
    restaurant_keyboard.add(types.InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data=f"cancel_order_{order.id}"
    ))
    restaurant_keyboard.adjust(1)

    # 3. Restoran guruhiga xabar
    order_text = (f"🚨 <b>YANGI BUYURTMA #{order.id}!</b>\n\n"
             f"<b>Tarkibi:</b>\n{items_text}\n"
             f"<b>Jami:</b> {formatted_total} so'm\n\n"
             f"<b>Mijoz:</b> {user.full_name}\n"
             f"<b>Tel:</b> {phone}\n"
             f"<b>Manzil:</b> {address_text}\n"
             f"<b>To'lov turi:</b> {payment_text}\n\n"
             f"<b>Status:</b> Kutilmoqda ⏳")

    if payment_method == "card_now" and payment_screenshot_url:
        restaurant_msg = await bot.send_photo(
            chat_id=restaurant.telegram_group_id,
            photo=payment_screenshot_url,
            caption=order_text,
            reply_markup=restaurant_keyboard.as_markup()
        )
    else:
        restaurant_msg = await bot.send_message(
            chat_id=restaurant.telegram_group_id,
            text=order_text,
            reply_markup=restaurant_keyboard.as_markup()
        )

    # 4. Restoran xabar ID sini saqlaymiz
    order.restaurant_msg_id = restaurant_msg.message_id
    await order.asave()

    # 5. Mijozga tasdiq xabari
    main_builder = ReplyKeyboardBuilder()
    main_builder.add(types.KeyboardButton(text="🛒 Zakaz berish"))
    main_builder.add(types.KeyboardButton(text="📜 Mening buyurtmalarim"))
    main_builder.adjust(2)

    confirm_text = (
        f"✅ <b>Buyurtmangiz #{order.id} qabul qilindi!</b>\n\n"
        f"Restoran buyurtmangizni ko'rib chiqmoqda. Tez orada javob beramiz."
    )

    await message_or_callback_msg.answer(
        confirm_text,
        reply_markup=main_builder.as_markup(resize_keyboard=True)
    )
    await state.clear()

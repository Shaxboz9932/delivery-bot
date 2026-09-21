from aiogram import Router, F, types
from aiogram.filters import Command
from orders.models import Order, OrderStatus, Courier

router = Router()

# Delivery xizmat haqi (har bir yetkazilgan zakaz uchun kuryerga beriladigan summa)
DELIVERY_FEE = 10000  # Masalan: 10,000 so'm


# 1. Kuryer buyurtmani birinchi bo'lib olganda
@router.callback_query(F.data.startswith("take_order_"))
async def take_order(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])
    courier_user = callback.from_user

    try:
        db_courier = await Courier.objects.aget(telegram_id=courier_user.id, is_active=True)
    except Courier.DoesNotExist:
        await callback.answer("Siz ro'yxatdan o'tmagansiz yoki faol emassiz! Iltimos, admin bilan bog'laning.", show_alert=True)
        return

    try:
        order = await Order.objects.select_related('restaurant').aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    # TEKSHIRUV: Agar buyurtmani boshqa kuryer olib bo'lgan bo'lsa
    if order.status in [OrderStatus.DELIVERING, OrderStatus.COMPLETED]:
        await callback.answer("Afsuski, ushbu buyurtmani boshqa kuryer olib bo'ldi!", show_alert=True)
        return

    # Buyurtmani ushbu kuryerga biriktiramiz
    order.status = OrderStatus.DELIVERING
    order.courier_tg_id = courier_user.id
    order.courier_name = db_courier.name
    order.courier_username = courier_user.username or ''
    await order.asave()

    complete_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="Yetkazib berdim ✅",
            callback_data=f"complete_order_{order.id}"
        )]
    ])

    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n"
        f"✅ <b>Buyurtmani kuryer oldi:</b> {db_courier.name} ({db_courier.phone_number})\n"
        f"<b>Status:</b> Yo'lda 🛵",
        reply_markup=complete_keyboard
    )

    # Mijozga bildirishnoma yuboramiz
    await bot.send_message(
        chat_id=order.customer_tg_id,
        text=f"🛵 Buyurtmangiz yo'lga chiqdi!\n\n"
             f"<b>Kuryer:</b> {db_courier.name}\n"
             f"<b>Telefon:</b> {db_courier.phone_number}"
    )

    # Restoran guruhiga bildirishnoma yuboramiz (Reply qilib)
    if order.restaurant_msg_id:
        try:
            await bot.send_message(
                chat_id=order.restaurant.telegram_group_id,
                text=f"🛵 <b>#{order.id} buyurtmani kuryer olib ketdi!</b>\n\n"
                     f"<b>Kuryer:</b> {db_courier.name}\n"
                     f"<b>Telefon:</b> {db_courier.phone_number}",
                reply_to_message_id=order.restaurant_msg_id
            )
        except Exception:
            pass

    await callback.answer("Buyurtma sizga biriktirildi!")


# 2. Kuryer buyurtmani topshirganda (Yetkazib berdim)
@router.callback_query(F.data.startswith("complete_order_"))
async def complete_order(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])
    courier = callback.from_user

    try:
        order = await Order.objects.select_related('restaurant').aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    # ASOSIY TEKSHIRUV: Bosgan kuryer ushbu buyurtmani olgan kuryermi?
    if order.courier_tg_id != courier.id:
        await callback.answer(
            "⛔️ Bu buyurtmani faqat uni qabul qilgan kuryer yakunlay oladi!",
            show_alert=True
        )
        return

    order.status = OrderStatus.COMPLETED
    # Naqd yoki yetkazib berilganda karta orqali to'lovlarda, pul olindi deb belgilaymiz
    if order.payment_method in ["cash", "card_delivery"]:
        order.is_paid = True
    await order.asave()

    await callback.message.edit_text(
        f"{callback.message.html_text}\n\n"
        f"🎉 <b>BUYURTMA MUVAFFAQIYATLI YETKAZILDI!</b>",
        reply_markup=None
    )

    # Mijozga bildirishnoma yuboramiz
    await bot.send_message(
        chat_id=order.customer_tg_id,
        text=f"✅ <b>Buyurtmangiz #{order.id} yetkazib berildi!</b>\n\n"
             f"Yoqimli ishtaha! Xizmatimizdan foydalanganingiz uchun rahmat. 😊"
    )

    # Restoran guruhiga bildirishnoma yuboramiz
    if order.restaurant_msg_id:
        try:
            await bot.send_message(
                chat_id=order.restaurant.telegram_group_id,
                text=f"✅ <b>#{order.id} buyurtma muvaffaqiyatli yetkazib berildi!</b>\n\n"
                     f"<b>Kuryer:</b> {order.courier_name}",
                reply_to_message_id=order.restaurant_msg_id
            )
        except Exception:
            pass

    await callback.answer("Buyurtma yakunlandi!")


# 3. Kuryer balansini ko'rsatish
@router.message(Command("balance"))
async def courier_balance_handler(message: types.Message):
    courier_id = message.from_user.id

    # Kuryer bajargan va COMPLETED bo'lgan buyurtmalarni filtri
    completed_orders = [
        o async for o in Order.objects.select_related('restaurant').filter(
            courier_tg_id=courier_id,
            status=OrderStatus.COMPLETED
        ).order_by('-created_at')
    ]

    total_count = len(completed_orders)

    if total_count == 0:
        await message.answer(
            "<b>🛵 Kuryer Paneli:</b>\n\n"
            "Siz hali birorta ham buyurtmani yetkazib bermagansiz."
        )
        return

    # Jami statistika
    courier_earnings = total_count * DELIVERY_FEE
    fmt_fee = f"{DELIVERY_FEE:,.0f}".replace(",", " ")
    fmt_earnings = f"{courier_earnings:,.0f}".replace(",", " ")

    summary_text = (
        f"📊 <b>KURYER BALANSI VA STATISTIKASI</b>\n\n"
        f"<b>Kuryer:</b> {message.from_user.full_name}\n"
        f"<b>Yetkazilgan buyurtmalar:</b> {total_count} ta\n"
        f"{'─' * 24}\n"
        f"💵 <b>Ish haqi ({fmt_fee} so'mdan):</b>\n"
        f"👉 <b>{fmt_earnings} so'm</b>"
    )
    await message.answer(summary_text)

    # Oxirgi 10 ta yetkazilgan buyurtmalar ro'yxati
    history_text = "📋 <b>Oxirgi yetkazilgan buyurtmalar:</b>\n\n"
    for idx, order in enumerate(completed_orders[:10], start=1):
        order_total = float(order.total_price)
        fmt_total = f"{order_total:,.0f}".replace(",", " ")
        order_date = order.created_at.strftime("%d.%m.%Y %H:%M")
        history_text += (
            f"{idx}. <b>#{order.id}</b> — {order.restaurant.name}\n"
            f"   💰 {fmt_total} so'm | 📅 {order_date}\n"
        )

    await message.answer(history_text)


# 4. Kuryerning barcha buyurtmalarini boshqa kuryer ko'rmasligi uchun
@router.message(Command("myorders"))
async def courier_orders_handler(message: types.Message):
    courier_id = message.from_user.id

    all_orders = [
        o async for o in Order.objects.select_related('restaurant').filter(
            courier_tg_id=courier_id
        ).order_by('-created_at')[:20]
    ]

    if not all_orders:
        await message.answer("Siz hali birorta ham buyurtma olmadingiz.")
        return

    status_dict = {
        OrderStatus.DELIVERING: "Yo'lda 🛵",
        OrderStatus.COMPLETED:  "Yetkazildi ✅",
        OrderStatus.CANCELLED:  "Bekor ❌",
    }

    text = f"📦 <b>{message.from_user.full_name} — Buyurtmalar tarixi:</b>\n\n"
    for order in all_orders:
        order_total = float(order.total_price)
        fmt_total = f"{order_total:,.0f}".replace(",", " ")
        order_date = order.created_at.strftime("%d.%m.%Y %H:%M")
        status_label = status_dict.get(order.status, order.status)
        text += (
            f"<b>#{order.id}</b> | {order.restaurant.name}\n"
            f"💰 {fmt_total} so'm | {status_label} | 📅 {order_date}\n\n"
        )

    await message.answer(text)
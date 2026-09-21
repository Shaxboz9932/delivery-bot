from aiogram import Router, F, types
from orders.models import Order, OrderStatus, OrderItem

router = Router()

def _build_items_keyboard(order_id: int, items: list) -> types.InlineKeyboardMarkup:
    """OrderItem ro'yxatidan toggle klaviaturasi yasaydi."""
    rows = []
    for item in items:
        icon = "❌" if item.is_removed else "✅"
        label = f"{icon} {item.item_name} ({item.quantity} dona)"
        rows.append([types.InlineKeyboardButton(
            text=label,
            callback_data=f"toggle_item_{order_id}_{item.id}"
        )])
    rows.append([types.InlineKeyboardButton(
        text="✔️ Tasdiqlash",
        callback_data=f"confirm_partial_{order_id}"
    )])
    rows.append([types.InlineKeyboardButton(
        text="◀️ Orqaga (bekor qilmasdan)",
        callback_data=f"back_to_order_{order_id}"
    )])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


# 6. Restoran "Qisman qabul" bosganda — taomlar ro'yxatini chiqarish
@router.callback_query(F.data.startswith("partial_accept_"))
async def partial_accept_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    items = [i async for i in OrderItem.objects.filter(order=order, is_removed=False)]
    if not items:
        await callback.answer("Bu buyurtmada taomlar yo'q!", show_alert=True)
        return

    keyboard = _build_items_keyboard(order_id, items)
    await callback.message.reply(
        "⚠️ <b>Qaysi taomlar mavjud emas?</b>\n"
        "Mavjud bo'lmagan taomni bosing — u ❌ belgisiga o'zgaradi.\n"
        "Tugagach <b>✔️ Tasdiqlash</b> ni bosing.",
        reply_markup=keyboard
    )
    await callback.answer()


# 7. Taomni ✅ / ❌ almashtirish (toggle)
@router.callback_query(F.data.startswith("toggle_item_"))
async def toggle_item(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    # toggle_item_{order_id}_{item_id}
    order_id = int(parts[2])
    item_id  = int(parts[3])

    try:
        item = await OrderItem.objects.aget(id=item_id)
    except OrderItem.DoesNotExist:
        await callback.answer("Taom topilmadi!", show_alert=True)
        return

    # Holatni almashtirish
    item.is_removed = not item.is_removed
    await item.asave()

    # Tugmalarni yangilash
    all_items = [i async for i in OrderItem.objects.filter(order_id=order_id)]
    keyboard = _build_items_keyboard(order_id, all_items)
    await callback.message.edit_reply_markup(reply_markup=keyboard)

    status = "❌ Olib tashlandi" if item.is_removed else "✅ Qaytarildi"
    await callback.answer(f"{item.item_name}: {status}")


# 8. Restoran "Tasdiqlash" bosganda — mijozga yangilangan xabar yuborish
@router.callback_query(F.data.startswith("confirm_partial_"))
async def confirm_partial(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.select_related('restaurant').aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    all_items = [i async for i in OrderItem.objects.filter(order=order)]
    removed_items = [i for i in all_items if i.is_removed]
    active_items  = [i for i in all_items if not i.is_removed]

    if not removed_items:
        await callback.answer(
            "Hech qanday taom olib tashlanmagan!\n"
            "Agar hammasi bor bo'lsa — 'Tayyor' tugmasini bosing.",
            show_alert=True
        )
        return

    if not active_items:
        await callback.answer(
            "Barcha taomlar olib tashlandi — buyurtmani bekor qiling!",
            show_alert=True
        )
        return

    # Yangi jami narxni hisoblash (yetkazib berish narxisiz)
    DELIVERY_FEE = 10_000.0
    new_subtotal = sum(float(i.item_price) * i.quantity for i in active_items)
    new_total    = new_subtotal + DELIVERY_FEE

    # Bazani yangilash
    order.status    = OrderStatus.PARTIAL_PENDING
    order.total_price = new_total
    await order.asave()

    # Mijozga yuborilacak xabar
    removed_text = ""
    for i in removed_items:
        removed_text += f"  ❌ {i.item_name} — {i.quantity} dona (olib tashlandi)\n"

    active_text = ""
    for i in active_items:
        price = float(i.item_price)
        subtotal = price * i.quantity
        fmt_subtotal = f"{subtotal:,.0f}".replace(",", " ")
        active_text += f"  ✅ {i.item_name} — {i.quantity} dona × {price:,.0f} = {fmt_subtotal} so'm\n"

    fmt_delivery = f"{DELIVERY_FEE:,.0f}".replace(",", " ")
    fmt_total    = f"{new_total:,.0f}".replace(",", " ")

    customer_text = (
        f"⚠️ <b>Buyurtmangiz #{order.id} bo'yicha o'zgarish!</b>\n\n"
        f"Restoran quyidagi taomlar mavjud emasligini bildirdi:\n"
        f"{removed_text}\n"
        f"<b>Yangilangan buyurtma:</b>\n"
        f"{active_text}\n"
        f"{'─' * 28}\n"
        f"🍽  <b>Taomlar summasi:</b>    {f'{new_subtotal:,.0f}'.replace(',', ' ')} so'm\n"
        f"🚗  <b>Yetkazib berish:</b>    {fmt_delivery} so'm\n"
        f"{'─' * 28}\n"
        f"💳  <b>Yangi jami:</b>        <b>{fmt_total} so'm</b>\n\n"
        f"Davom etishni xohlaysizmi?"
    )

    customer_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="✅ Roziman, davom etsin",
            callback_data=f"partial_confirm_{order.id}"
        )],
        [types.InlineKeyboardButton(
            text="❌ Buyurtmani bekor qilish",
            callback_data=f"partial_cancel_{order.id}"
        )]
    ])

    await bot.send_message(
        chat_id=order.customer_tg_id,
        text=customer_text,
        reply_markup=customer_keyboard
    )

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(
        f"✅ Mijozga yangilangan buyurtma yuborildi.\n"
        f"Mijoz javobi kutilmoqda..."
    )
    await callback.answer("Mijozga xabar yuborildi!")

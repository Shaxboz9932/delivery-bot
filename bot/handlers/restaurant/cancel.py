from aiogram import Router, F, types
from orders.models import Order, OrderStatus

router = Router()

# 3. Restoran buyurtmani bekor qilmoqchi bo'lganda (Sabab so'rash)
@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    # Bekor qilish sabablari uchun knopkalar
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Maxsulot qolmagan", callback_data=f"creason_noproduct_{order.id}")],
        [types.InlineKeyboardButton(text="Pul tushmagan", callback_data=f"creason_nomoney_{order.id}")],
        [types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back_to_order_{order.id}")]
    ])

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Bekor qilish sababini tanlang")

# 4. Orqaga qaytish (Bekor qilishdan voz kechish)
@router.callback_query(F.data.startswith("back_to_order_"))
async def back_to_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[-1])
    try:
        order = await Order.objects.aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return
        
    if order.status == OrderStatus.CREATED:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Qabul qilish ✅", callback_data=f"accept_order_{order.id}")],
            [types.InlineKeyboardButton(text="Bekor qilish ❌", callback_data=f"cancel_order_{order.id}")]
        ])
    elif order.status == OrderStatus.WAITING_PAYMENT:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Bekor qilish ❌", callback_data=f"cancel_order_{order.id}")]
        ])
    elif order.status == OrderStatus.ACCEPTED:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Oshxona tayyorladi (Kuryerga yuborish) 🚀", callback_data=f"ready_order_{order.id}")],
            [types.InlineKeyboardButton(text="Bekor qilish ❌", callback_data=f"cancel_order_{order.id}")]
        ])
    else:
        await callback.message.edit_reply_markup(reply_markup=None)
        return
        
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

# 5. Haqiqiy bekor qilish (Sabab tanlanganda)
@router.callback_query(F.data.startswith("creason_"))
async def process_cancel_reason(callback: types.CallbackQuery, bot):
    parts = callback.data.split("_")
    reason_code = parts[1]
    order_id = int(parts[2])

    try:
        order = await Order.objects.aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    reason_text = "Maxsulot qolmagan" if reason_code == "noproduct" else "Pul tushmagan"

    order.status = OrderStatus.CANCELLED
    await order.asave()

    cancel_msg = f"❌ <b>BUYURTMA BEKOR QILINDI!</b>\n<i>Sabab: {reason_text}</i>"
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{callback.message.html_text}\n\n{cancel_msg}",
            reply_markup=None
        )
    else:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n{cancel_msg}",
            reply_markup=None
        )


    # Mijozga bildirishnoma
    await bot.send_message(
        chat_id=order.customer_tg_id,
        text=f"❌ <b>Buyurtmangiz #{order.id} bekor qilindi.</b>\n"
             f"<i>Sababi: {reason_text}</i>"
    )

    await callback.answer("Buyurtma bekor qilindi!")

from aiogram import Router, F, types
from orders.models import Order, OrderStatus
from .utils import COURIER_GROUP_ID

router = Router()

# 2. Taom tayyor bo'lganda (Kuryerlar guruhiga yuborish)
@router.callback_query(F.data.startswith("ready_order_"))
async def ready_order(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.select_related('restaurant').aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    order.status = OrderStatus.READY
    await order.asave()

    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{callback.message.html_text}\n\n<b>Status:</b> Taom tayyor! Kuryer kutilmoqda 🛵",
            reply_markup=None  # Tugmalarni olib tashlaymiz
        )
    else:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n<b>Status:</b> Taom tayyor! Kuryer kutilmoqda 🛵",
            reply_markup=None  # Tugmalarni olib tashlaymiz
        )

    payment_method_dict = {
        "cash": "Naqd (Yetkazib berilganda pul olinadi)",
        "card_delivery": "Karta orqali (Yetkazib berilganda pul olinadi)",
        "card_now": "Karta orqali hoziroq (To'langan)"
    }
    payment_text = payment_method_dict.get(order.payment_method, "Noma'lum")

    courier_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="Buyurtmani olish 🚗",
            callback_data=f"take_order_{order.id}"
        )]
    ])

    # Kuryerlar guruhiga xabar yuboramiz
    courier_msg = await bot.send_message(
        chat_id=COURIER_GROUP_ID,
        text=f"🚨 <b>Yangi Buyurtma #{order.id}!</b>\n\n"
             f"<b>Restoran:</b> {order.restaurant.name}\n"
             f"<b>Manzil:</b> {order.address_text}\n"
             f"<b>Jami narx:</b> {order.total_price:,.0f} so'm\n"
             f"<b>To'lov holati:</b> {payment_text}",
        reply_markup=courier_keyboard
    )

    order.courier_msg_id = courier_msg.message_id
    await order.asave()

    await callback.answer("Kuryerlarga xabar yuborildi!")

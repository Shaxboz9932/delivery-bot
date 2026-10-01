from aiogram import Router, F, types
from orders.models import Order, OrderStatus

router = Router()

# 1. Restoran buyurtmani qabul qilganda
@router.callback_query(F.data.startswith("accept_order_"))
async def accept_order(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.select_related('restaurant').aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    # Agar karta orqali hoziroq to'lov bo'lsa va hali to'lanmagan bo'lsa -> 2-bosqichli to'lov
    if order.payment_method == "card_now" and not order.is_paid:
        order.status = OrderStatus.WAITING_PAYMENT
        await order.asave()

        cancel_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text="Bekor qilish ❌",
                callback_data=f"cancel_order_{order.id}"
            )]
        ])

        status_text = f"{callback.message.html_text}\n\n<b>Status:</b> Restoran tasdiqladi! Mijozdan to'lov kutilmoqda 💳⏳"
        if callback.message.photo:
            await callback.message.edit_caption(caption=status_text, reply_markup=cancel_keyboard)
        else:
            await callback.message.edit_text(status_text, reply_markup=cancel_keyboard)

        formatted_total = f"{float(order.total_price):,.0f}".replace(",", " ")
        card_info = f"<b>Karta raqami:</b> <code>{order.restaurant.card_number}</code>\n<b>Karta egasi:</b> {order.restaurant.card_owner_name}" if order.restaurant.card_number else "Karta ma'lumotlari kiritilmagan. Iltimos admin bilan bog'laning."

        await bot.send_message(
            chat_id=order.customer_tg_id,
            text=f"✅ <b>Restoran buyurtmangizni #{order.id} tasdiqladi!</b>\n\n"
                 f"Jami to'lov summasi: <b>{formatted_total} so'm</b>\n\n"
                 f"{card_info}\n\n"
                 f"Iltimos, to'lovni amalga oshirganingizdan so'ng <b>to'lov skrinshotini shu yerga yuboring.</b>"
        )
        await callback.answer("Buyurtma tasdiqlandi! Mijozga to'lov rekvizitlari yuborildi.")
        return

    # Naqd yoki Yetkazib berganda karta (yoki allaqachon to'langan)
    order.status = OrderStatus.ACCEPTED
    await order.asave()

    # Restoran guruhidagi tugma: Tayyor / Qisman qabul / Bekor
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="🚀 Oshxona tayyorladi (Kuryerga yuborish)",
                callback_data=f"ready_order_{order.id}"
            )
        ],
        # [
        #     types.InlineKeyboardButton(
        #         text="⚠️ Qisman qabul (taom yo'q)",
        #         callback_data=f"partial_accept_{order.id}"
        #     )
        # ],
        [
            types.InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data=f"cancel_order_{order.id}"
            )
        ]
    ])

    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{callback.message.html_text}\n\n<b>Status:</b> Qabul qilindi, tayyorlanmoqda 👨‍🍳",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n<b>Status:</b> Qabul qilindi, tayyorlanmoqda 👨‍🍳",
            reply_markup=keyboard
        )

    await bot.send_message(
        chat_id=order.customer_tg_id,
        text=f"✅ <b>Buyurtmangiz (#{order.id}) qabul qilindi!</b>\nRestoran tayyorlashni boshladi 👨‍🍳"
    )
    await callback.answer("Buyurtma qabul qilindi!")


# 2. Restoran to'lov chekini tasdiqlaganda
@router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    order.is_paid = True
    order.status = OrderStatus.ACCEPTED
    await order.asave()

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="🚀 Oshxona tayyorladi (Kuryerga yuborish)",
                callback_data=f"ready_order_{order.id}"
            )
        ],
        # [
        #     types.InlineKeyboardButton(
        #         text="⚠️ Qisman qabul (taom yo'q)",
        #         callback_data=f"partial_accept_{order.id}"
        #     )
        # ],
        [
            types.InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data=f"cancel_order_{order.id}"
            )
        ]
    ])

    if callback.message.photo:
        await callback.message.edit_caption(
            caption=f"{callback.message.html_text}\n\n<b>Status:</b> To'lov tasdiqlandi, tayyorlanmoqda 👨‍🍳",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n<b>Status:</b> To'lov tasdiqlandi, tayyorlanmoqda 👨‍🍳",
            reply_markup=keyboard
        )

    await bot.send_message(
        chat_id=order.customer_tg_id,
        text=f"✅ <b>Buyurtmangiz (#{order.id}) to'lovi tasdiqlandi!</b>\n"
             f"Oshxona buyurtmani tayyorlashni boshladi."
    )

    await callback.answer("To'lov tasdiqlandi!")

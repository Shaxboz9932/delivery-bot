from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from orders.models import Order, OrderItem, OrderStatus
from .cart import view_cart_handler

router = Router()

# Buyurtmalar tarixini ko'rsatish
@router.message(F.text == "📜 Mening buyurtmalarim")
async def show_order_history(message: types.Message):
    customer_id = message.from_user.id

    orders = [
        o async for o in Order.objects.filter(customer_tg_id=customer_id)
        .select_related('restaurant')
        .order_by('-created_at')[:5]
    ]

    if not orders:
        await message.answer("Sizda hali amalga oshirilgan buyurtmalar mavjud emas.")
        return

    status_dict = {
        OrderStatus.CREATED: "Kutilmoqda ⏳",
        OrderStatus.WAITING_PAYMENT: "To'lov kutilmoqda 💳",
        OrderStatus.PARTIAL_PENDING: "Qisman qabul — javob kutilmoqda ⚠️",
        OrderStatus.ACCEPTED: "Qabul qilindi 👨‍🍳",
        OrderStatus.READY: "Tayyor 🛵",
        OrderStatus.DELIVERING: "Yo'lda 🚗",
        OrderStatus.COMPLETED: "Yetkazib berildi ✅",
        OrderStatus.CANCELLED: "Bekor qilindi ❌",
    }

    for order in orders:
        total_val = float(order.total_price)
        formatted_total = f"{total_val:,.0f}".replace(",", " ") if total_val.is_integer() else f"{total_val:,.2f}".replace(",", " ")
        created_time = order.created_at.strftime("%Y-%m-%d %H:%M")

        text = (
            f"📦 <b>Buyurtma #{order.id}</b>\n"
            f"<b>Restoran:</b> {order.restaurant.name}\n"
            f"<b>Sana:</b> {created_time}\n"
            f"<b>Jami:</b> {formatted_total} so'm\n"
            f"<b>Status:</b> {status_dict.get(order.status, order.status)}\n"
        )

        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="🔄 Qayta buyurtma berish",
            callback_data=f"reorder_{order.id}"
        ))

        await message.answer(text, reply_markup=builder.as_markup())


# Qayta buyurtma berish (Re-Order)
@router.callback_query(F.data.startswith("reorder_"))
async def reorder_handler(callback: types.CallbackQuery, state: FSMContext):
    old_order_id = int(callback.data.split("_")[-1])

    try:
        old_order = await Order.objects.select_related('restaurant').aget(id=old_order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    old_items = [item async for item in OrderItem.objects.filter(order=old_order)]

    if not old_items:
        await callback.answer(
            "Bu buyurtma uchun taomlar ma'lumotlari saqlanmagan.",
            show_alert=True
        )
        return

    cart = {}
    for item in old_items:
        cart[str(item.id)] = {
            'name': item.item_name,
            'price': float(item.item_price),
            'quantity': item.quantity
        }

    await state.update_data(cart=cart, restaurant_id=old_order.restaurant.id)
    await callback.answer("✅ Buyurtmangiz savatga qayta yuklandi!")

    await view_cart_handler(callback, state)


# ═══════════════════════════════════════════════
# QISMAN QABUL — MIJOZ JAVOB HANDLERLARI
# ═══════════════════════════════════════════════

# 9. Mijoz "Roziman, davom etsin" bosganda
@router.callback_query(F.data.startswith("partial_confirm_"))
async def partial_confirm_handler(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.select_related('restaurant').aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order.status != OrderStatus.PARTIAL_PENDING:
        await callback.answer("Bu buyurtma allaqachon qayta ishlangan.", show_alert=True)
        return

    order.status = OrderStatus.ACCEPTED
    await order.asave()

    try:
        await callback.message.edit_text(
            callback.message.html_text + "\n\n<b>Siz tasdiqladi! Restoran tayyorlamoqda.</b>",
            reply_markup=None
        )
    except Exception:
        pass

    await bot.send_message(
        chat_id=order.restaurant.telegram_group_id,
        text=f"<b>Mijoz buyurtma #{order.id} yangilangan holatini tasdiqladi!</b>\nIltimos, buyurtmani tayyorlashni boshlang."
    )
    await callback.answer("Tasdiqlandi! Restoran buyurtmangizni tayyorlaydi.")


# 10. Mijoz "Buyurtmani bekor qilish" bosganda
@router.callback_query(F.data.startswith("partial_cancel_"))
async def partial_cancel_handler(callback: types.CallbackQuery, bot):
    order_id = int(callback.data.split("_")[-1])

    try:
        order = await Order.objects.select_related('restaurant').aget(id=order_id)
    except Order.DoesNotExist:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order.status != OrderStatus.PARTIAL_PENDING:
        await callback.answer("Bu buyurtma allaqachon qayta ishlangan.", show_alert=True)
        return

    order.status = OrderStatus.CANCELLED
    await order.asave()

    try:
        await callback.message.edit_text(
            callback.message.html_text + "\n\nBuyurtma bekor qilindi.",
            reply_markup=None
        )
    except Exception:
        pass

    await bot.send_message(
        chat_id=order.restaurant.telegram_group_id,
        text=f"Mijoz buyurtma #{order.id} ni bekor qildi.\nSabab: Mijoz yangilangan buyurtma shartlariga rozi bolmadi."
    )
    await callback.answer("Buyurtmangiz bekor qilindi.")

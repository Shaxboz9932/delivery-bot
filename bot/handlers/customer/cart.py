from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from orders.models import MenuItem

router = Router()

# 6. Taomni Savatga qo'shish
@router.callback_query(F.data.startswith("add_to_cart_"))
async def add_to_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[-1])

    try:
        item = await MenuItem.objects.select_related('restaurant').aget(id=item_id)
    except MenuItem.DoesNotExist:
        await callback.answer("Taom topilmadi!", show_alert=True)
        return

    data = await state.get_data()
    cart = data.get("cart", {})

    current_rest_id = data.get("restaurant_id")
    if current_rest_id and current_rest_id != item.restaurant.id:
        await callback.answer(
            "Siz faqat bitta restorandan buyurtma bera olasiz! Avvalgi savatni tozalang.",
            show_alert=True
        )
        return

    if str(item_id) in cart:
        cart[str(item_id)]['quantity'] += 1
    else:
        cart[str(item_id)] = {
            'name': item.name,
            'price': float(item.price),
            'quantity': 1
        }

    await state.update_data(cart=cart, restaurant_id=item.restaurant.id)

    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text=f"➕ Yana qo'shish",
        callback_data=f"add_to_cart_{item.id}"
    ))
    builder.add(types.InlineKeyboardButton(
        text=f"🛒 Savatni ko'rish ({len(cart)} xil)",
        callback_data="view_cart"
    ))
    builder.adjust(1)

    await callback.answer(f"✅ {item.name} savatga qo'shildi!")
    if callback.message.photo:
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    else:
        try:
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        except:
            pass


# 7. Savatni ko'rish va miqdorini boshqarish
@router.message(F.text == "🛒 Savatni ko'rish")
async def view_cart_message_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await message.answer("Savatchangiz bo'sh!")
        return

    DELIVERY_FEE = 10_000.0

    text = "🛒 <b>Sizning savatchangiz:</b>\n\n"
    subtotal = 0.0

    builder = InlineKeyboardBuilder()

    for item_id, item in cart.items():
        item_price = float(item['price'])
        item_total = item_price * item['quantity']
        subtotal += item_total

        fmt_price = f"{item_price:,.0f}".replace(",", " ") if item_price.is_integer() else f"{item_price:,.2f}".replace(",", " ")
        fmt_total = f"{item_total:,.0f}".replace(",", " ") if item_total.is_integer() else f"{item_total:,.2f}".replace(",", " ")

        text += f"• <b>{item['name']}</b>: {item['quantity']} dona x {fmt_price} = <b>{fmt_total} so'm</b>\n"

        builder.row(
            types.InlineKeyboardButton(text="➖", style="danger", callback_data=f"dec_{item_id}"),
            types.InlineKeyboardButton(text=f"{item['name']} ({item['quantity']})", callback_data="ignore"),
            types.InlineKeyboardButton(text="➕", style="success", callback_data=f"inc_{item_id}")
        )

    grand_total = subtotal + DELIVERY_FEE
    fmt_subtotal  = f"{subtotal:,.0f}".replace(",", " ") if subtotal.is_integer() else f"{subtotal:,.2f}".replace(",", " ")
    fmt_delivery  = f"{DELIVERY_FEE:,.0f}".replace(",", " ")
    fmt_grand     = f"{grand_total:,.0f}".replace(",", " ") if grand_total.is_integer() else f"{grand_total:,.2f}".replace(",", " ")

    text += (
        f"\n{'─' * 28}\n"
        f"🍽  <b>Taomlar summasi:</b>        {fmt_subtotal} so'm\n"
        f"🚗  <b>Yetkazib berish:</b>         10 000 yoki 15 000 so'm\n"
        f"{'─' * 28}\n"
        f"<i>Yakuniy summa hudud tanlangandan so'ng hisoblanadi.</i>"
    )

    builder.row(types.InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart"))
    builder.row(types.InlineKeyboardButton(text="✅ Buyurtmani rasmiylashtirish", callback_data="checkout"))

    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "view_cart")
async def view_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await callback.answer("Savatchangiz bo'sh!", show_alert=True)
        return

    DELIVERY_FEE = 10_000.0

    text = "🛒 <b>Sizning savatchangiz:</b>\n\n"
    subtotal = 0.0

    builder = InlineKeyboardBuilder()

    for item_id, item in cart.items():
        item_price = float(item['price'])
        item_total = item_price * item['quantity']
        subtotal += item_total

        fmt_price = f"{item_price:,.0f}".replace(",", " ") if item_price.is_integer() else f"{item_price:,.2f}".replace(",", " ")
        fmt_total = f"{item_total:,.0f}".replace(",", " ") if item_total.is_integer() else f"{item_total:,.2f}".replace(",", " ")

        text += f"• <b>{item['name']}</b>: {item['quantity']} dona x {fmt_price} = <b>{fmt_total} so'm</b>\n"

        builder.row(
            types.InlineKeyboardButton(text="➖", style="danger", callback_data=f"dec_{item_id}"),
            types.InlineKeyboardButton(text=f"{item['name']} ({item['quantity']})", callback_data="ignore"),
            types.InlineKeyboardButton(text="➕", style="success", callback_data=f"inc_{item_id}")
        )

    grand_total = subtotal + DELIVERY_FEE
    fmt_subtotal  = f"{subtotal:,.0f}".replace(",", " ") if subtotal.is_integer() else f"{subtotal:,.2f}".replace(",", " ")
    fmt_delivery  = f"{DELIVERY_FEE:,.0f}".replace(",", " ")
    fmt_grand     = f"{grand_total:,.0f}".replace(",", " ") if grand_total.is_integer() else f"{grand_total:,.2f}".replace(",", " ")

    text += (
        f"\n{'─' * 28}\n"
        f"🍽  <b>Taomlar summasi:</b>        {fmt_subtotal} so'm\n"
        f"🚗  <b>Yetkazib berish:</b>         10 000 yoki 15 000 so'm\n"
        f"{'─' * 28}\n"
        f"<i>Yakuniy summa hudud tanlangandan so'ng hisoblanadi.</i>"
    )

    builder.row(types.InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart"))
    builder.row(types.InlineKeyboardButton(text="✅ Buyurtmani rasmiylashtirish", callback_data="checkout"))

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup())
    else:
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        except:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


# 8. Taom miqdorini oshirish (+) va kamaytirish (-)
@router.callback_query(F.data.startswith(("inc_", "dec_")))
async def update_quantity_handler(callback: types.CallbackQuery, state: FSMContext):
    action, item_id = callback.data.split("_")
    data = await state.get_data()
    cart = data.get("cart", {})

    if item_id in cart:
        if action == "inc":
            cart[item_id]['quantity'] += 1
        elif action == "dec":
            cart[item_id]['quantity'] -= 1
            if cart[item_id]['quantity'] <= 0:
                del cart[item_id]

    await state.update_data(cart=cart)

    if not cart:
        await state.clear()
        await callback.message.edit_text("🛒 Savatchangiz bo'shatildi.")
    else:
        await view_cart_handler(callback, state)


# 9. Savatni tozalash
@router.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🗑 Savatingiz tozalandi.")
    await callback.answer("Savat tozalandi")


# 10. Neitral tugma (miqdor bosilganda xato bermasligi uchun)
@router.callback_query(F.data == "ignore")
async def ignore_handler(callback: types.CallbackQuery):
    await callback.answer()

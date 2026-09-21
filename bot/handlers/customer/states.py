from aiogram.fsm.state import StatesGroup, State

# Checkout jarayoni uchun holatlar
class OrderCheckout(StatesGroup):
    waiting_for_delivery_zone = State()
    waiting_for_location = State()
    waiting_for_phone = State()
    waiting_for_payment_method = State()
    waiting_for_payment_screenshot = State()

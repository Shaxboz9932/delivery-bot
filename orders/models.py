# models.py
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    CUSTOMER = 'customer', 'Mijoz'
    COURIER = 'courier', 'Kuryer'


class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Yetkazib berilganda (Naqd)'
    CARD_DELIVERY = 'card_delivery', 'Yetkazib berilganda (Karta)'
    CARD_NOW = 'card_now', 'Karta orqali hoziroq'

class OrderStatus(models.TextChoices):
    CREATED = 'created', 'Kutilmoqda'
    WAITING_PAYMENT = 'waiting_payment', 'To\'lov kutilmoqda'
    PARTIAL_PENDING = 'partial_pending', 'Qisman qabul — Mijoz javobi kutilmoqda'
    ACCEPTED = 'accepted', 'Qabul qilindi'
    READY = 'ready', 'Tayyor (Kuryer kutilmoqda)'
    DELIVERING = 'delivering', 'Yo\'lda'
    COMPLETED = 'completed', 'Yetkazildi'
    CANCELLED = 'cancelled', 'Bekor qilindi'



class Restaurant(models.Model):
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, null=True, blank=True, help_text="Restoran bilan aloqa uchun telefon raqami")
    telegram_group_id = models.BigIntegerField(help_text="Restoran Telegram guruhi ID'si")
    card_number = models.CharField(max_length=20, null=True, blank=True, help_text="Restoranning plastik karta raqami")
    card_owner_name = models.CharField(max_length=150, null=True, blank=True, help_text="Karta egasining ism-familiyasi")
    is_active = models.BooleanField(default=True)
    opening_time = models.TimeField(
        null=True, blank=True,
        help_text="Ish boshlash vaqti (masalan: 09:00)"
    )
    closing_time = models.TimeField(
        null=True, blank=True,
        help_text="Ish tugash vaqti (masalan: 23:00)"
    )

    def is_open(self):
        """Restoran hozir ochiqmi? (Asia/Tashkent vaqti bo'yicha)"""
        if not self.opening_time or not self.closing_time:
            # Ish vaqti kiritilmagan bo'lsa — har doim ochiq deb hisoblaymiz
            return True
        now = timezone.localtime(timezone.now()).time()
        if self.opening_time <= self.closing_time:
            # Oddiy holat: 09:00 – 23:00
            return self.opening_time <= now <= self.closing_time
        else:
            # Yarim tundan o'tuvchi vaqt: 22:00 – 02:00
            return now >= self.opening_time or now <= self.closing_time

    def __str__(self):
        return self.name


class Order(models.Model):
    customer_tg_id = models.BigIntegerField()
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    courier_tg_id = models.BigIntegerField(null=True, blank=True)
    courier_name = models.CharField(max_length=150, null=True, blank=True, help_text="Kuryerning to'liq ismi (snapshot)")
    courier_username = models.CharField(max_length=100, null=True, blank=True, help_text="Kuryerning Telegram username'i (snapshot)")

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.CREATED)
    payment_method = models.CharField(max_length=150, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    payment_screenshot_url = models.CharField(max_length=500, null=True, blank=True, help_text="To'lov skrinshoti Telegram file_id yoki URL")
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/', null=True, blank=True, help_text="To'lov skrinshoti rasmi")
    is_paid = models.BooleanField(default=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    address_text = models.TextField(blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Telegram xabarlarini tahrirlash (editMessageText) uchun message_id lar
    restaurant_msg_id = models.IntegerField(null=True, blank=True)
    courier_msg_id = models.IntegerField(null=True, blank=True)
    partial_accept_msg_id = models.IntegerField(null=True, blank=True, help_text="Mijozga yuborilgan 'Qisman qabul' xabari ID si")


    def __str__(self):
        return f"Buyrutma № {self.id}"


class OrderItem(models.Model):
    """Buyurtmadagi har bir taomning snapshot'i (saqlangan nusxasi)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    item_name = models.CharField(max_length=100, help_text="Taom nomi (snapshot)")
    item_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Taom narxi (snapshot)")
    quantity = models.PositiveIntegerField(default=1)
    is_removed = models.BooleanField(default=False, help_text="Restoran tomonidan olib tashlangan taom")

    @property
    def subtotal(self):
        return self.item_price * self.quantity

    def __str__(self):
        return f"#{self.order.id} — {self.item_name} x{self.quantity}"


class Category(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100) # Masalan: Fast Food, Ichimliklar, Milliy taomlar

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"

class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    name = models.CharField(max_length=100) # Masalan: Lavash, Cheeseburger
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text="Taom faol (mavjud) bo'lsa True, vaqtincha mavjud emas bo'lsa False")

    def __str__(self):
        return f"{self.name} ({self.price} so'm)"

class MenuItemImage(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='menu_images/', help_text='Taom rasmi')
    is_main = models.BooleanField(default=False, help_text='Asosiy rasm (faqat 1 ta bo_lishi tavsiya etiladi)')

    def __str__(self):
        return f'{self.menu_item.name} rasmi'


class Courier(models.Model):
    name = models.CharField(max_length=150, verbose_name="Kuryer ismi")
    phone_number = models.CharField(max_length=20, verbose_name="Telefon raqami")
    telegram_username = models.CharField(max_length=100, null=True, blank=True, verbose_name="Telegram username")
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True, verbose_name="Telegram ID")
    is_active = models.BooleanField(default=True, verbose_name="Faol kuryer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kuryer"
        verbose_name_plural = "Kuryerlar"

    def __str__(self):
        return f"{self.name} ({self.phone_number})"

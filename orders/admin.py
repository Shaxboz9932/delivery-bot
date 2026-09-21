# orders/admin.py
from django.contrib import admin
from .models import Restaurant, Category, MenuItem, Order, MenuItemImage, OrderItem, Courier

class MenuItemImageInline(admin.TabularInline):
    model = MenuItemImage
    extra = 1

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('item_name', 'item_price', 'quantity', 'subtotal')
    fields = ('item_name', 'item_price', 'quantity')
    can_delete = False

    def subtotal(self, obj):
        return f"{obj.subtotal:,.0f} so'm"
    subtotal.short_description = "Jami"

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone_number', 'telegram_group_id', 'opening_time', 'closing_time', 'is_active')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'restaurant')

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'restaurant', 'category', 'price', 'is_active')
    list_filter = ('restaurant', 'category', 'is_active')
    inlines = [MenuItemImageInline]

from django.utils.safestring import mark_safe

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_tg_id', 'restaurant', 'courier_name', 'status', 'total_price', 'is_paid', 'screenshot_preview', 'created_at')
    list_filter = ('status', 'is_paid', 'restaurant')
    search_fields = ('courier_name', 'courier_username', 'customer_tg_id')
    readonly_fields = ('screenshot_preview',)
    inlines = [OrderItemInline]

    def screenshot_preview(self, obj):
        if obj.payment_screenshot:
            return mark_safe(f'<a href="{obj.payment_screenshot.url}" target="_blank"><img src="{obj.payment_screenshot.url}" width="100" style="max-height:120px; border-radius:6px; object-fit:cover;" /></a>')
        return "Yo'q"
    screenshot_preview.short_description = "To'lov skrinshoti"

@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone_number', 'telegram_username', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'phone_number', 'telegram_username')


from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from orders.models.coat import CoatMeasurement
from .models import *


# ------------------------------
# PRODUCT TYPE
# ------------------------------
@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# ------------------------------
# CLIENT PHOTOS (INLINE IN ORDER)
# ------------------------------
class ClientPhotoInline(admin.TabularInline):
    model = ClientPhoto
    extra = 3
    max_num = 3


# ------------------------------
# ORDER ITEM PHOTOS (INLINE)
# ------------------------------
class OrderItemPhotoInline(admin.TabularInline):
    model = OrderItemPhoto
    extra = 1


# ------------------------------
# ORDER ITEMS (INLINE IN ORDER)
# ------------------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


# ------------------------------
# ORDER ADMIN
# ------------------------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        'order_number',
        'first_name',
        'last_name',
        'contact_method',
        'phone',
        'status',
        'ready_date',
        'urgent_status',
        'created_at',
        'total_amount',
    )

    list_filter = (
        'contact_method',
        'is_urgent',
        'status',
        'created_at',
        'ready_date',
        'country',  # ✅ FIXED (was shipping_country)
    )

    search_fields = (
        'order_number',
        'first_name',
        'last_name',
        'phone',
        'email',
        'city',
        'postcode',
        'country',
    )

    date_hierarchy = 'created_at'

    readonly_fields = ('created_at',)

    fieldsets = (
        ('Order Info', {
            'fields': (
                'order_number',
                'created_at',
                'status',
            )
        }),

        ('Customer Info', {
            'fields': (
                'first_name',
                'last_name',
                'contact_method',
                'phone',
                'email',
            )
        }),

        ('Shipping Address', {
            'fields': (
                'street_address',
                ('city', 'postcode'),
                ('state', 'country'),
            )
        }),

        ('Production Info', {
            'fields': (
                'ready_date',
                'is_urgent',
                'total_amount',
            )
        }),

        ('Notes', {
            'fields': ('note',),
        }),
    )

    inlines = [OrderItemInline, ClientPhotoInline]

    def urgent_status(self, obj):
        return "🚨 URGENT" if obj.is_urgent else "Normal"

    urgent_status.short_description = "Priority"

    

# ------------------------------
# ORDER ITEM ADMIN
# ------------------------------
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order',
        'product_type',
        'product_name',
        'quantity',
        'price'
    )

    list_filter = ('product_type',)
    search_fields = ('product_name',)
    inlines = [OrderItemPhotoInline]




# ------------------------------
# BASE MEASUREMENT ADMIN
# ------------------------------
@admin.register(BaseMeasurement)
class BaseMeasurementAdmin(admin.ModelAdmin):
    list_display = ('order_item', 'created_at')
    search_fields = ('order_item__product_name',)
    


# ------------------------------
# MEASUREMENT MODELS
# ------------------------------
@admin.register(SuitMeasurement)
class SuitMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(JacketMeasurement)
class JacketMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(CoatMeasurement)
class CoatMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(ShirtMeasurement)
class ShirtMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(PantsMeasurement)
class PantsMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(ShortsMeasurement)
class ShortsMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)



@admin.register(VestMeasurement)
class VestMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(SkirtMeasurement)
class SkirtMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(DressMeasurement)
class DressMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)


@admin.register(BlouseMeasurement)
class BlouseMeasurementAdmin(admin.ModelAdmin):
    list_display = ('base',)
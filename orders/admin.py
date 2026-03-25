from django.contrib import admin
from django.utils.html import format_html
from .models import *


# ------------------------------
# TENANT ADMIN (required for CustomUserAdmin autocomplete_fields)
# ------------------------------
from .models import Tenant

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "subdomain")
    search_fields = ("name", "subdomain")  # REQUIRED for autocomplete_fields

    

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
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100"/>', obj.image.url)
        return "-"
    image_preview.short_description = "Preview"


# ------------------------------
# SCRATCH NOTE (INLINE)
# ------------------------------
class ScratchNoteInline(admin.TabularInline):
    model = ScratchNote
    extra = 1
    readonly_fields = ["preview"]

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="200"/>', obj.image.url)
        return "-"
    preview.short_description = "Preview"


# ------------------------------
# ORDER ITEM PHOTOS (INLINE)
# ------------------------------
class OrderItemPhotoInline(admin.TabularInline):
    model = OrderItemPhoto
    extra = 1
    readonly_fields = ["preview"]

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100"/>', obj.image.url)
        return "-"
    preview.short_description = "Preview"


# ------------------------------
# ORDER ITEMS (INLINE IN ORDER)
# ------------------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    inlines = [OrderItemPhotoInline]  # allow photo inline here


# ------------------------------
# ORDER ADMIN
# ------------------------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'first_name', 'last_name', 'contact_method',
        'phone', 'status', 'ready_date', 'urgent_status', 'created_at', 'total_amount'
    )
    list_filter = ('contact_method', 'is_urgent', 'status', 'created_at', 'ready_date', 'country')
    search_fields = ('order_number', 'first_name', 'last_name', 'phone', 'email', 'city', 'postcode', 'country')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Order Info', {'fields': ('order_number', 'created_at', 'status')}),
        ('Customer Info', {'fields': ('first_name', 'last_name', 'contact_method', 'phone', 'email')}),
        ('Shipping Address', {'fields': ('street_address', ('city', 'postcode'), ('state', 'country'))}),
        ('Production Info', {'fields': ('ready_date', 'is_urgent', 'total_amount')}),
        ('Notes', {'fields': ('note',)}),
    )

    inlines = [OrderItemInline, ClientPhotoInline, ScratchNoteInline]

    def urgent_status(self, obj):
        return "🚨 URGENT" if obj.is_urgent else "Normal"
    urgent_status.short_description = "Priority"

    # Make status field editable only for staff
    def get_readonly_fields(self, request, obj=None):
        ro_fields = list(self.readonly_fields)
        if not request.user.is_staff:
            ro_fields.append('status')
        return ro_fields


# ------------------------------
# ORDER ITEM ADMIN
# ------------------------------
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_type', 'product_name', 'quantity', 'price')
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
measurement_models = [
    SuitMeasurement, JacketMeasurement, CoatMeasurement, ShirtMeasurement,
    PantsMeasurement, ShortsMeasurement, VestMeasurement, SkirtMeasurement,
    DressMeasurement, BlouseMeasurement, NoMeasurement, ShoesMeasurement, BeltMeasurement
]

for model in measurement_models:
    @admin.register(model)
    class MeasurementAdmin(admin.ModelAdmin):
        list_display = ('base',)
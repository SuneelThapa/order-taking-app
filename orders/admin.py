from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Tenant, ReferralSource, Client, StaffProfile,
    Order, CancellationRecord, Delivery, Payment,
    OrderStaff, ClientSignature, EmailLog,
    ProductType, OrderItem, OrderItemPhoto,
    ClientPhoto, ScratchNote, BaseMeasurement,
    SuitMeasurement, JacketMeasurement, CoatMeasurement,
    ShirtMeasurement, PantsMeasurement, ShortsMeasurement,
    VestMeasurement, SkirtMeasurement, DressMeasurement,
    BlouseMeasurement, NoMeasurement, ShoesMeasurement, BeltMeasurement,
)


# -------------------------------------------------------
@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'subdomain', 'is_active')
    search_fields = ('name', 'subdomain')


# -------------------------------------------------------
@admin.register(ReferralSource)
class ReferralSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'phone', 'is_active')
    list_filter = ('type', 'is_active')
    search_fields = ('name', 'phone')


# -------------------------------------------------------
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'acquisition_channel', 'marketing_consent', 'is_active', 'created_at')
    list_filter = ('acquisition_channel', 'marketing_consent', 'is_active')
    search_fields = ('name', 'phone', 'email')
    raw_id_fields = ('referral_source', 'referred_by')
    readonly_fields = ('created_at',)


# -------------------------------------------------------
@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employment_type', 'base_salary', 'default_commission_percentage', 'join_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')


# -------------------------------------------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('thb_equivalent', 'created_at')


class OrderStaffInline(admin.TabularInline):
    model = OrderStaff
    extra = 0


class ClientPhotoInline(admin.TabularInline):
    model = ClientPhoto
    extra = 0
    readonly_fields = ('preview',)

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="80"/>', obj.image.url)
        return '-'
    preview.short_description = 'Preview'


class ScratchNoteInline(admin.TabularInline):
    model = ScratchNote
    extra = 0
    readonly_fields = ('preview', 'created_at')

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="150"/>', obj.image.url)
        return '-'
    preview.short_description = 'Preview'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'client', 'status', 'is_urgent',
        'fitting_date', 'ready_date', 'delivery_date',
        'total_amount', 'created_at'
    )
    list_filter = ('status', 'is_urgent', 'tenant', 'created_at')
    search_fields = ('order_number', 'client__name', 'client__phone', 'client__email')
    raw_id_fields = ('client', 'parent_order')
    readonly_fields = ('order_number', 'created_at', 'balance_due')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Order', {'fields': ('order_number', 'tenant', 'client', 'parent_order', 'status', 'is_urgent', 'created_at')}),
        ('Dates', {'fields': ('fitting_date', 'ready_date', 'delivery_date')}),
        ('Address Snapshot', {'fields': ('street_address', 'city', 'state', 'postcode', 'country')}),
        ('Financials', {'fields': ('total_amount', 'balance_due')}),
        ('Notes', {'fields': ('note', 'internal_notes')}),
    )

    inlines = [OrderItemInline, PaymentInline, OrderStaffInline, ClientPhotoInline, ScratchNoteInline]

    def balance_due(self, obj):
        return obj.balance_due
    balance_due.short_description = 'Balance Due (THB)'


# -------------------------------------------------------
@admin.register(CancellationRecord)
class CancellationRecordAdmin(admin.ModelAdmin):
    list_display = ('order', 'cancellation_type', 'resolution', 'canceled_at', 'canceled_by')
    list_filter = ('cancellation_type', 'resolution')
    search_fields = ('order__order_number',)
    readonly_fields = ('canceled_at',)


# -------------------------------------------------------
@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('order', 'type', 'hotel_name', 'room_number')
    list_filter = ('type',)
    search_fields = ('order__order_number', 'hotel_name')


# -------------------------------------------------------
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'original_amount', 'currency', 'thb_equivalent', 'method', 'type', 'recorded_by', 'created_at')
    list_filter = ('currency', 'method', 'type')
    search_fields = ('order__order_number',)
    readonly_fields = ('thb_equivalent', 'created_at')


# -------------------------------------------------------
@admin.register(ClientSignature)
class ClientSignatureAdmin(admin.ModelAdmin):
    list_display = ('order', 'signed_at', 'ip_address')
    readonly_fields = ('signed_at',)


# -------------------------------------------------------
@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('client', 'subject', 'status', 'sent_at', 'sent_by')
    list_filter = ('status',)
    search_fields = ('client__name', 'subject')
    readonly_fields = ('sent_at',)


# -------------------------------------------------------
@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_model')
    search_fields = ('name',)


# -------------------------------------------------------
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_type', 'product_name', 'quantity', 'price', 'total_price')
    search_fields = ('product_name', 'order__order_number')
    list_filter = ('product_type',)


# -------------------------------------------------------
@admin.register(BaseMeasurement)
class BaseMeasurementAdmin(admin.ModelAdmin):
    list_display = ('order_item', 'created_at')


# -------------------------------------------------------
measurement_models = [
    SuitMeasurement, JacketMeasurement, CoatMeasurement, ShirtMeasurement,
    PantsMeasurement, ShortsMeasurement, VestMeasurement, SkirtMeasurement,
    DressMeasurement, BlouseMeasurement, NoMeasurement, ShoesMeasurement,
    BeltMeasurement,
]

for model in measurement_models:
    @admin.register(model)
    class MeasurementAdmin(admin.ModelAdmin):
        list_display = ('base',)
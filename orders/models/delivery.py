from django.db import models
from .order import Order


class Delivery(models.Model):

    DELIVERY_TYPES = [
        ('pickup', 'In-store Pickup'),
        ('hotel',  'Hotel Delivery'),
        ('ship',   'Ship to Address'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    type  = models.CharField(max_length=20, choices=DELIVERY_TYPES, default='pickup')

    # Hotel delivery
    hotel_name  = models.CharField(max_length=255, blank=True, null=True)
    room_number = models.CharField(max_length=50,  blank=True, null=True)

    # Shipping address
    shipping_street  = models.CharField(max_length=255, blank=True, null=True)
    shipping_city    = models.CharField(max_length=100, blank=True, null=True)
    shipping_state   = models.CharField(max_length=100, blank=True, null=True)
    shipping_postcode = models.CharField(max_length=20, blank=True, null=True)
    shipping_country = models.CharField(max_length=100, blank=True, null=True)

    delivery_notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delivery'
        verbose_name_plural = 'Deliveries'

    def __str__(self):
        return f"{self.get_type_display()} — {self.order.order_number}"
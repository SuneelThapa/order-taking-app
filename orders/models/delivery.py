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

    # Proof of delivery/shipment — protects against chargebacks
    proof_image = models.ImageField(
        upload_to='delivery_proofs/',
        null=True, blank=True,
        help_text="Photo proof of delivery or shipping receipt"
    )

    class Meta:
        verbose_name = 'Delivery'
        verbose_name_plural = 'Deliveries'

    def __str__(self):
        return f"{self.get_type_display()} — {self.order.order_number}"

    def _resolved_address_parts(self):
        """
        Returns the ship-to address as a dict, falling back through:
        1) This delivery's own shipping_* fields (Step 5 override)
        2) The order's address snapshot (copied from client at creation)
        3) The client's current profile address
        Never returns None for any field — always empty string instead.
        """
        order  = self.order
        client = getattr(order, 'client', None)

        def pick(*values):
            for v in values:
                if v:
                    return v
            return ''

        return {
            'street':   pick(self.shipping_street,   getattr(order, 'street_address', ''), getattr(client, 'street_address', '')),
            'city':     pick(self.shipping_city,      getattr(order, 'city', ''),           getattr(client, 'city', '')),
            'state':    pick(self.shipping_state,     getattr(order, 'state', ''),          getattr(client, 'state', '')),
            'postcode': pick(self.shipping_postcode,  getattr(order, 'postcode', ''),       getattr(client, 'postcode', '')),
            'country':  pick(self.shipping_country,   getattr(order, 'country', ''),        getattr(client, 'country', '')),
        }

    @property
    def resolved_address(self):
        """Dict with street/city/state/postcode/country — never None, falls back to order/client address."""
        return self._resolved_address_parts()

    @property
    def full_shipping_address(self):
        """Single formatted multi-line address string, empty if nothing on file anywhere."""
        a = self._resolved_address_parts()
        line2 = ', '.join(p for p in [a['city'], a['state'], a['postcode']] if p)
        parts = [a['street'], line2, a['country']]
        return '\n'.join(p for p in parts if p)

    @property
    def has_resolved_address(self):
        return bool(self.full_shipping_address)
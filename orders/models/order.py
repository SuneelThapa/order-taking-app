from django.conf import settings
from django.db import models
from django.utils import timezone
from .client import Client


# Shared currency choices used by Order (quoted total) and Payment (actual payment)
CURRENCY_CHOICES = [
    ('THB',    'Thai Baht (THB)'),
    ('USD',    'US Dollar (USD)'),
    ('AUD',    'Australian Dollar (AUD)'),
    ('SGD',    'Singapore Dollar (SGD)'),
    ('EUR',    'Euro (EUR)'),
    ('crypto', 'Cryptocurrency'),
]


class Order(models.Model):

    STATUS_CHOICES = [
        ('new',         'New'),
        ('pending',     'Pending'),
        ('processing',  'Processing'),
        ('ready',       'Ready'),
        ('alterations', 'Alterations'),
        ('delivered',   'Delivered'),
        ('canceled',    'Canceled'),
    ]

    # Identity
    order_number = models.CharField(max_length=20, unique=True, db_index=True, blank=True)
    external_order_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="Existing order number from previous system (optional)"
    )
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    # Tenant
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE, related_name='orders')

    # Client
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT,
        related_name='orders', db_index=True
    )

    # Reorder / remake chain
    parent_order = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='child_orders',
    )

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='new', db_index=True
    )

    # Where the client is currently staying (contact for this visit)
    hotel_name  = models.CharField(max_length=255, blank=True, null=True)
    room_number = models.CharField(max_length=50,  blank=True, null=True)

    # Address snapshot — auto-copied from Client at creation, staff can override
    street_address = models.CharField(max_length=255, blank=True, null=True)
    city           = models.CharField(max_length=100, blank=True, null=True)
    state          = models.CharField(max_length=100, blank=True, null=True)
    postcode       = models.CharField(max_length=20,  blank=True, null=True)
    country        = models.CharField(max_length=100, blank=True, null=True)

    # Key dates
    departure_date = models.DateField(blank=True, null=True)
    fitting_date   = models.DateField(blank=True, null=True)
    fitting_time   = models.TimeField(blank=True, null=True)
    ready_date     = models.DateField(blank=True, null=True)
    ready_time     = models.TimeField(blank=True, null=True)
    delivery_date  = models.DateField(blank=True, null=True)
    delivery_time  = models.TimeField(blank=True, null=True)

    # Quoted total — stored in whatever currency was agreed with the client
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Quoted price in the selected currency"
    )
    total_currency = models.CharField(
        max_length=10, choices=CURRENCY_CHOICES, default='THB',
        help_text="Currency of the quoted total amount"
    )
    total_locked    = models.BooleanField(default=False)
    total_locked_at = models.DateTimeField(null=True, blank=True)
    total_locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='locked_orders',
    )

    # Notes
    note           = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(blank=True, null=True)

    is_urgent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'external_order_number'],
                condition=models.Q(external_order_number__isnull=False) &
                          ~models.Q(external_order_number=''),
                name='unique_external_order_number_per_tenant',
            )
        ]

    def save(self, *args, **kwargs):
        # Normalize empty string to None for external_order_number
        if self.external_order_number == '':
            self.external_order_number = None
        if not self.order_number:
            from django.db import transaction
            import time
            year_prefix = timezone.now().strftime("%y")
            for attempt in range(5):
                try:
                    with transaction.atomic():
                        last_order = (
                            Order.objects
                            .select_for_update()
                            .filter(order_number__startswith=year_prefix)
                            .order_by('-order_number')
                            .first()
                        )
                        new_number = (int(last_order.order_number[2:]) + 1) if last_order else 1
                        self.order_number = f"{year_prefix}{new_number:04d}"
                        if not self.pk and self.client_id and not self.street_address:
                            self._copy_client_address()
                        super().save(*args, **kwargs)
                        return
                except Exception as e:
                    if attempt < 4:
                        time.sleep(0.05)
                        self.order_number = ''
                        continue
                    raise
        else:
            if not self.pk and self.client_id and not self.street_address:
                self._copy_client_address()
            super().save(*args, **kwargs)

    def _copy_client_address(self):
        c = self.client
        self.street_address = c.street_address
        self.city           = c.city
        self.state          = c.state
        self.postcode       = c.postcode
        self.country        = c.country

    @property
    def balance_due(self):
        """
        Returns remaining balance.
        Note: compares total_amount directly against sum of thb_equivalent payments.
        For non-THB totals this is a rough indicator; accurate balance is in payments tab.
        """
        from django.db.models import Sum
        collected = self.payments.aggregate(total=Sum('thb_equivalent'))['total'] or 0
        return self.total_amount - collected

    @property
    def is_canceled(self):
        return self.status == 'canceled'

    def __str__(self):
        return self.order_number

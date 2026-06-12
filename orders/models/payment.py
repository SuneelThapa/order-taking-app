from django.db import models
from django.conf import settings
from .order import Order, CURRENCY_CHOICES


class Payment(models.Model):

    PAYMENT_METHODS = [
        ('cash',                 'Cash'),
        ('card',                 'Card'),
        ('stripe',               'Stripe'),
        ('app_banking',          'App Banking'),
        ('direct_bank_transfer', 'Direct Bank Transfer'),
        ('crypto',               'Cryptocurrency'),
    ]

    PAYMENT_TYPES = [
        ('deposit',   'Deposit'),
        ('redeposit', 'Re-deposit'),
        ('balance',   'Balance'),
        ('full',      'Full Payment'),
        ('refund',    'Refund'),
    ]

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='payments', db_index=True
    )

    # Original amount in whatever currency was paid
    original_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Negative value = refund"
    )
    currency = models.CharField(
        max_length=10, choices=CURRENCY_CHOICES, default='THB'
    )

    # Exchange rate to THB at time of payment.
    # THB=1 always. Crypto=fixed agreed rate. Others=rate on the day.
    exchange_rate_to_thb = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        help_text="THB=1. Crypto=agreed fixed rate. Others=today's rate."
    )

    # Locked at save time — never recomputed. Used for all commission and reporting.
    thb_equivalent = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="original_amount × exchange_rate_to_thb. Stored once, never updated."
    )

    method = models.CharField(max_length=30, choices=PAYMENT_METHODS, default='cash')
    type   = models.CharField(max_length=20, choices=PAYMENT_TYPES,  default='deposit')

    notes = models.TextField(blank=True, null=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT, related_name='payments_recorded'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def save(self, *args, **kwargs):
        # Always compute and lock thb_equivalent on save
        self.thb_equivalent = self.original_amount * self.exchange_rate_to_thb
        super().save(*args, **kwargs)

    @property
    def is_refund(self):
        return self.type == "refund" or self.original_amount < 0

    def __str__(self):
        direction = "Refund" if self.is_refund else "Payment"
        return (
            f"{direction} {self.original_amount} {self.currency}"
            f" — {self.order.order_number}"
        )
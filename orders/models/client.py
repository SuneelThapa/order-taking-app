from django.db import models
from django.core.validators import RegexValidator

from .referral_source import ReferralSource


# E.164 format: +[country code][number] e.g. +66812345678
phone_validator = RegexValidator(
    regex=r'^\+[1-9]\d{7,14}$',
    message="Phone must be in E.164 format, e.g. +66812345678"
)


class Client(models.Model):

    CONTACT_METHODS = [
        ('whatsapp', 'WhatsApp'),
        ('viber', 'Viber'),
        ('email', 'Email'),
        ('phone', 'Phone'),
    ]

    ACQUISITION_CHANNELS = [
        ('walk_in', 'Walk-in'),
        ('online', 'Online'),
        ('tuktuk', 'Tuk-Tuk'),
        ('reference', 'Reference'),
    ]

    # Core identity
    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(
        max_length=20,
        validators=[phone_validator],
        db_index=True,
        help_text="E.164 format, e.g. +66812345678"
    )
    email = models.EmailField(blank=True, null=True, db_index=True)
    contact_method = models.CharField(
        max_length=20,
        choices=CONTACT_METHODS,
        default='whatsapp'
    )

    # Acquisition
    acquisition_channel = models.CharField(
        max_length=20,
        choices=ACQUISITION_CHANNELS,
        default='walk_in',
        db_index=True
    )
    referral_source = models.ForeignKey(
        ReferralSource,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clients',
        help_text="Populate when acquisition channel is Tuk-Tuk"
    )
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='referrals',
        help_text="Populate when acquisition channel is Reference"
    )

    # Default address (copied to Order as snapshot at creation)
    street_address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postcode = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    # Notes
    notes = models.TextField(
        blank=True, null=True,
        help_text="Internal notes about this client (fabric preferences, fit notes, etc.)"
    )

    # Marketing
    marketing_consent = models.BooleanField(
        default=False,
        help_text="Client has consented to receive marketing communications (PDPA)"
    )

    # Meta
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'

    def __str__(self):
        return f"{self.name} ({self.phone})"

    def get_whatsapp_url(self):
        """Returns a wa.me link using the stored E.164 number (strip the +)."""
        if self.phone:
            return f"https://wa.me/{self.phone.lstrip('+')}"
        return None

    def total_spent(self):
        """Sum of thb_equivalent of all non-refund payments across all orders."""
        from django.db.models import Sum
        from orders.models.payment import Payment
        return (
            Payment.objects
            .filter(order__client=self, original_amount__gt=0)
            .aggregate(total=Sum('thb_equivalent'))['total'] or 0
        )

from django.db import models
from django.conf import settings

from .order import Order


class CancellationRecord(models.Model):

    CANCELLATION_TYPES = [
        ('client_request', 'Client Request'),
        ('non_payment', 'Non-payment'),
        ('remake', 'Remake'),
        ('other', 'Other'),
    ]

    RESOLUTION_CHOICES = [
        ('none', 'No Resolution'),
        ('remake', 'Remake Order Created'),
        ('alteration', 'Alteration Applied'),
        ('partial_refund', 'Partial Refund'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='cancellation'
    )

    # Who / when
    canceled_at = models.DateTimeField(auto_now_add=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cancellations_made'
    )

    # Why
    cancellation_type = models.CharField(
        max_length=20,
        choices=CANCELLATION_TYPES,
        default='client_request'
    )
    cancel_reason = models.TextField(
        help_text="Detailed reason for cancellation"
    )

    # Resolution
    resolution = models.CharField(
        max_length=20,
        choices=RESOLUTION_CHOICES,
        default='none'
    )
    resolution_notes = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    # Owner approval — required for partial_refund
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cancellations_approved',
        help_text="Owner approval required for partial refund resolutions"
    )

    class Meta:
        verbose_name = 'Cancellation Record'
        verbose_name_plural = 'Cancellation Records'

    def __str__(self):
        return f"Cancellation — {self.order.order_number}"
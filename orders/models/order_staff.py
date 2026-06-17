from django.db import models
from django.conf import settings
from django.db.models import Sum

from .order import Order


class OrderStaff(models.Model):

    ROLE_CHOICES = [
        ('owner',    'Owner'),
        ('salesman', 'Salesman'),
        ('helper',   'Helper'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='staff_assignments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='order_assignments'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='salesman'
    )

    # Defaulted from StaffProfile.default_commission_percentage at time of adding.
    # Admin can override per order.
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0,
        help_text="Commission % for this person on this order. Defaulted from StaffProfile."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'user')
        verbose_name = 'Order Staff'
        verbose_name_plural = 'Order Staff'

    # ------------------------------------------------------------------
    # Commission calculation
    # Commission is earned ONLY on payments collected while order is NOT canceled.
    # Pre-cancellation payments already earned stay earned.
    # ------------------------------------------------------------------
    def commission_earned(self):
        """
        Returns the commission amount in THB earned by this staff member
        on this order, based on actual collected payments (thb_equivalent).

        For canceled orders: only payments made BEFORE the cancellation
        count toward commission.
        """
        from .payment import Payment
        from .cancellation_record import CancellationRecord

        payments_qs = Payment.objects.filter(
            order=self.order,
            original_amount__gt=0  # exclude refunds
        )

        # If canceled, only count payments before cancellation timestamp
        if self.order.is_canceled:
            try:
                canceled_at = self.order.cancellation.canceled_at
                payments_qs = payments_qs.filter(created_at__lt=canceled_at)
            except CancellationRecord.DoesNotExist:
                pass

        collected_thb = payments_qs.aggregate(
            total=Sum('thb_equivalent')
        )['total'] or 0

        return round(collected_thb * self.commission_percentage / 100, 2)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.get_role_display()} on {self.order.order_number}"
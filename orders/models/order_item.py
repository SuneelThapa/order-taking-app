from django.db import models
from django.core.validators import MinValueValidator
from .order import Order
from .product_type import ProductType


class OrderItem(models.Model):

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', db_index=True)
    product_type = models.ForeignKey(ProductType, on_delete=models.PROTECT, related_name='items', db_index=True)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)

    # Nullable — price may not be known at order creation time.
    # total_amount on Order is the authoritative price set on the Finish step.
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Optional — leave blank if price not yet confirmed"
    )

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    @property
    def total_price(self):
        if self.price is None:
            return 0
        return self.quantity * self.price

    def __str__(self):
        return f"{self.product_name} — {self.order.order_number}"
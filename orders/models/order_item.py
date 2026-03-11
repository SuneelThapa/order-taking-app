from django.db import models
from .order import Order
from .product_type import ProductType
from django.core.validators import MinValueValidator




class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        db_index=True
    )

    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.PROTECT,
        related_name='items',
        db_index=True
    )

   

    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])


    def __str__(self):
        return f"{self.product_name} - {self.order.order_number}"

    @property
    def total_price(self):
        return self.quantity * self.price
from django.db import models
from .order_item import OrderItem


class OrderItemPhoto(models.Model):
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='photos'
    )

    image = models.ImageField(upload_to='order_item_photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order_item.product_name} photo"
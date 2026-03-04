from django.db import models
from .order import Order


class ClientPhoto(models.Model):

    PHOTO_TYPES = [
        ('front', 'Front'),
        ('side', 'Side'),
        ('back', 'Back'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='client_photos'
    )

    photo_type = models.CharField(max_length=20, choices=PHOTO_TYPES)
    image = models.ImageField(upload_to='client_photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'photo_type')

    def __str__(self):
        return f"{self.order.order_number} - {self.photo_type}"
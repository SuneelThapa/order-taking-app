from django.db import models

from .order import Order


class ClientSignature(models.Model):

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='signature'
    )

    image = models.ImageField(upload_to='signatures/')

    # Auto timestamp — this is the legal record
    signed_at = models.DateTimeField(auto_now_add=True)

    # IP address of the device used to sign
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        verbose_name = 'Client Signature'
        verbose_name_plural = 'Client Signatures'

    def __str__(self):
        return f"Signature — {self.order.order_number} at {self.signed_at}"

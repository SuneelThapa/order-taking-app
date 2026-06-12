from django.db import models

from .order import Order


class ScratchNote(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='scratch_notes',
        db_index=True
    )
    image = models.ImageField(upload_to='scratch_notes/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Scratch Note'
        verbose_name_plural = 'Scratch Notes'

    def __str__(self):
        return f"Scratch note — {self.order.order_number}"

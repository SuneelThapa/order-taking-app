from django.db import models


class TargetItem(models.Model):
    """
    Represents a garment type that variation types apply to.
    e.g. Jacket, Shirt, Pants, Coat, Dress
    """
    name  = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = "Target Item"
        verbose_name_plural = "Target Items"
        ordering            = ["order", "name"]

    def __str__(self):
        return self.name
from django.db import models


class FabricZone(models.Model):
    """
    A fabric zone for a specific product type.
    Admin defines defaults (e.g. Jacket → Body, Lapel, Collar, Sleeve,
    Lining Body, Lining Sleeve). Staff can add custom zones per bill.
    """
    product_type = models.ForeignKey(
        "orders.ProductType",
        on_delete=models.CASCADE,
        related_name="fabric_zones"
    )
    name         = models.CharField(
        max_length=100,
        help_text="e.g. Body, Lapel, Collar, Sleeve, Lining Body, Lining Sleeve"
    )
    order        = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = "Fabric Zone"
        verbose_name_plural = "Fabric Zones"
        unique_together     = ("product_type", "name")
        ordering            = ["product_type", "order", "name"]

    def __str__(self):
        return f"{self.product_type.name} — {self.name}"
from django.db import models


class VariationType(models.Model):
    """
    A category of style choice for a garment.
    e.g. Lapel Style, Vent Style, Collar Style, Cuff Style
    """
    name         = models.CharField(max_length=100, unique=True)
    description  = models.TextField(blank=True, null=True)
    target_items = models.ManyToManyField(
        "orders.TargetItem",
        related_name="variation_types",
        help_text="Which garment types this variation applies to."
    )
    order        = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = "Variation Type"
        verbose_name_plural = "Variation Types"
        ordering            = ["order", "name"]

    def __str__(self):
        return self.name


class VariationOption(models.Model):
    """
    A specific option within a VariationType, with an optional style diagram image.
    e.g. Peak Lapel, Double Vent, French Cuff
    """
    type        = models.ForeignKey(
        VariationType,
        on_delete=models.CASCADE,
        related_name="options"
    )
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image       = models.ImageField(
        upload_to="variation_options/%Y/%m/",
        blank=True, null=True,
        help_text="Style diagram image shown on the production bill."
    )
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = "Variation Option"
        verbose_name_plural = "Variation Options"
        unique_together     = ("type", "name")
        ordering            = ["type", "order", "name"]

    def __str__(self):
        return f"{self.type.name} — {self.name}"
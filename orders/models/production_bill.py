from django.db import models
from django.conf import settings


class ProductionBill(models.Model):
    """
    One production bill per OrderItem.
    Locked after confirmation — no edits without admin override.
    """
    GENDER_CHOICES = [
        ("men",    "Men"),
        ("ladies", "Ladies"),
        ("unisex", "Unisex"),
    ]
    STATUS_CHOICES = [
        ("draft",     "Draft"),
        ("confirmed", "Confirmed"),
    ]

    order_item   = models.OneToOneField(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="production_bill"
    )
    gender       = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default="men"
    )
    status       = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )
    sent_to_factory    = models.BooleanField(default=False)
    sent_to_factory_at = models.DateTimeField(null=True, blank=True)
    sent_to_factory_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bills_sent_to_factory"
    )
    notes        = models.TextField(
        blank=True,
        help_text="General notes for the factory."
    )
    created_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="production_bills_created"
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="production_bills_confirmed"
    )

    class Meta:
        verbose_name        = "Production Bill"
        verbose_name_plural = "Production Bills"
        ordering            = ["-created_at"]

    @property
    def is_locked(self):
        return self.status == "confirmed"

    def __str__(self):
        return (
            f"Bill #{self.pk} — "
            f"{self.order_item.product_type.name if self.order_item.product_type else 'Item'} "
            f"({self.get_status_display()})"
        )


class FabricSet(models.Model):
    """
    One fabric set per physical piece in the order.
    e.g. OrderItem quantity=3 → 3 FabricSets (one per jacket).
    """
    bill         = models.ForeignKey(
        ProductionBill,
        on_delete=models.CASCADE,
        related_name="fabric_sets"
    )
    piece_number = models.PositiveIntegerField(
        help_text="1, 2, 3 … matches quantity of OrderItem"
    )
    label        = models.CharField(
        max_length=100,
        blank=True,
        help_text='Optional label e.g. "Groom", "Best Man"'
    )

    class Meta:
        verbose_name        = "Fabric Set"
        verbose_name_plural = "Fabric Sets"
        unique_together     = ("bill", "piece_number")
        ordering            = ["bill", "piece_number"]

    def __str__(self):
        label = f" ({self.label})" if self.label else ""
        return f"Piece {self.piece_number}{label}"


class FabricZoneEntry(models.Model):
    """
    Fabric details for one zone within a FabricSet.
    Zone can be a predefined FabricZone or a custom free-text label.
    """
    fabric_set   = models.ForeignKey(
        FabricSet,
        on_delete=models.CASCADE,
        related_name="zone_entries"
    )
    zone         = models.ForeignKey(
        "orders.FabricZone",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Predefined zone. Leave blank to use custom zone label."
    )
    zone_label   = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom zone name (used when zone FK is blank)."
    )
    fabric_code  = models.CharField(max_length=100, blank=True)
    color        = models.CharField(max_length=100, blank=True)
    notes        = models.CharField(max_length=255, blank=True)
    order        = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = "Fabric Zone Entry"
        verbose_name_plural = "Fabric Zone Entries"
        ordering            = ["fabric_set", "order"]

    @property
    def display_zone(self):
        """Return zone name — predefined name takes priority."""
        return self.zone.name if self.zone else self.zone_label

    def __str__(self):
        return f"{self.display_zone}: {self.fabric_code} {self.color}".strip()


class BillStyleSelection(models.Model):
    """
    The chosen style option for one VariationType on a ProductionBill.
    Shared across all pieces (same lapel style for all 3 jackets).
    """
    bill             = models.ForeignKey(
        ProductionBill,
        on_delete=models.CASCADE,
        related_name="style_selections"
    )
    variation_type   = models.ForeignKey(
        "orders.VariationType",
        on_delete=models.CASCADE,
        related_name="bill_selections"
    )
    chosen_option    = models.ForeignKey(
        "orders.VariationOption",
        on_delete=models.CASCADE,
        related_name="bill_selections"
    )

    class Meta:
        verbose_name        = "Bill Style Selection"
        verbose_name_plural = "Bill Style Selections"
        unique_together     = ("bill", "variation_type")

    def __str__(self):
        return f"{self.variation_type.name}: {self.chosen_option.name}"


class Monogram(models.Model):
    """
    Optional monogram per piece (FabricSet).
    Each piece can have different initials, style, colour and position.
    """
    fabric_set = models.OneToOneField(
        FabricSet,
        on_delete=models.CASCADE,
        related_name="monogram"
    )
    text       = models.CharField(
        max_length=20,
        help_text='Initials e.g. "MML"'
    )
    style      = models.ForeignKey(
        "orders.VariationOption",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="monogram_uses",
        help_text="Style diagram option e.g. Script, Block, Old English"
    )
    color      = models.CharField(max_length=100, blank=True,
                                  help_text='e.g. "Gold", "Navy Blue"')
    position   = models.CharField(max_length=100, blank=True,
                                  help_text='e.g. "Chest", "Cuff", "Collar"')

    class Meta:
        verbose_name        = "Monogram"
        verbose_name_plural = "Monograms"

    def __str__(self):
        return f"{self.text} — {self.style.name if self.style else 'No style'} {self.color}"
from django.db import models


class BodyMeasurement(models.Model):
    """
    Full body measurements taken once per order item.
    Gender-aware: ladies fields are stored but only shown when gender=ladies.
    Linked per item (not per order) so a package order can have
    a suit for him and a dress for her in the same order.
    """
    GENDER_CHOICES = [
        ('men',    'Men'),
        ('ladies', 'Ladies'),
    ]

    order_item = models.OneToOneField(
        'orders.OrderItem',
        on_delete=models.CASCADE,
        related_name='body_measurement'
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default='men',
    )

    # ── Universal body measurements ──────────────────────
    neck     = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Neck')
    shoulder = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Shoulder')
    sleeve   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Sleeve')
    biceps   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Biceps')
    chest    = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Chest')
    stomach  = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Stomach')
    waist    = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Waist')
    hips     = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Hips')
    height   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Height')
    weight   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Weight')

    # ── Ladies-specific ──────────────────────────────────
    high_chest = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='High Chest')
    upper_hips = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Upper Hips')
    deep_front = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Deep Front')
    deep_back = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Deep Back')
    shoulder_to_middle_breast = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Shoulder to Middle Breast')
    shoulder_to_under_breast = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Shoulder to Under Breast')
    middle_breast_to_middle_breast = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Middle Breast to Middle Breast')

    class Meta:
        verbose_name        = 'Body Measurement'
        verbose_name_plural = 'Body Measurements'

    def __str__(self):
        return f'{self.get_gender_display()} — {self.order_item}'
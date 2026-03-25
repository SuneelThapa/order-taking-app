from django.db import models
from .base_measurement import BaseMeasurement


class ShoesMeasurement(models.Model):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='shoes_measurement'
    )

    foot_length = models.FloatField(null=True, blank=True)
    foot_width = models.FloatField(null=True, blank=True)
    foot_instep = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Shoes Measurement"
        verbose_name_plural = "Shoes Measurements"

    def __str__(self):
        return "Shoes Measurements"
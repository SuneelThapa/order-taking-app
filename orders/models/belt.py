from django.db import models
from .base_measurement import BaseMeasurement


class BeltMeasurement(models.Model):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='belt_measurement'
    )

    belt_waist = models.FloatField(null=True, blank=True)
    

    class Meta:
        verbose_name = "Belt Measurement"
        verbose_name_plural = "Belt Measurements"

    def __str__(self):
        return "Belt Measurements"
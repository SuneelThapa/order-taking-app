from django.db import models
from .base_measurement import BaseMeasurement


class NoMeasurement(models.Model):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='no_measurement'
    )

    

    class Meta:
        verbose_name = "No Measurement"
        verbose_name_plural = "No Measurements"

    def __str__(self):
        return "No measurement required"
from django.db import models
from .base_measurement import BaseMeasurement


class ShortsMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='shorts')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Shorts'
        verbose_name_plural = 'Shorts'
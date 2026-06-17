from django.db import models
from .base_measurement import BaseMeasurement


class SkirtMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='skirt')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Skirt'
        verbose_name_plural = 'Skirts'
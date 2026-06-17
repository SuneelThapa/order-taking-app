from django.db import models
from .base_measurement import BaseMeasurement


class VestMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='vest')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Vest'
        verbose_name_plural = 'Vests'
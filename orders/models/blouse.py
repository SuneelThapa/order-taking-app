from django.db import models
from .base_measurement import BaseMeasurement


class BlouseMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='blouse')
    neck   = models.FloatField(null=True, blank=True, verbose_name='Neck')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Blouse'
        verbose_name_plural = 'Blouses'
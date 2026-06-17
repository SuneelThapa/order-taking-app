from django.db import models
from .base_measurement import BaseMeasurement


class CoatMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='coat')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Coat'
        verbose_name_plural = 'Coats'
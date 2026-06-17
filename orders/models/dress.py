from django.db import models
from .base_measurement import BaseMeasurement


class DressMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='dress')
    neck   = models.FloatField(null=True, blank=True, verbose_name='Neck')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Dress'
        verbose_name_plural = 'Dresses'
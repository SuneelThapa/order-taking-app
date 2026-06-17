from django.db import models
from .base_measurement import BaseMeasurement


class ShirtMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='shirt')
    neck   = models.FloatField(null=True, blank=True, verbose_name='Neck')
    sleeve = models.FloatField(null=True, blank=True, verbose_name='Sleeve')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Shirt'
        verbose_name_plural = 'Shirts'
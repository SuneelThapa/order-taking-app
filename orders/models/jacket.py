from django.db import models
from .base_measurement import BaseMeasurement


class JacketMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='jacket')
    sleeve = models.FloatField(null=True, blank=True, verbose_name='Sleeve')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Jacket'
        verbose_name_plural = 'Jackets'
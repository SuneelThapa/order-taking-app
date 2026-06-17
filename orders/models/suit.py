from django.db import models
from .base_measurement import BaseMeasurement


class SuitMeasurement(models.Model):
    base         = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='suit')
    sleeve       = models.FloatField(null=True, blank=True, verbose_name='Sleeve')
    jacket_length = models.FloatField(null=True, blank=True, verbose_name='Jacket Length')
    pants_length  = models.FloatField(null=True, blank=True, verbose_name='Pants Length')

    class Meta:
        verbose_name = 'Suit'
        verbose_name_plural = 'Suits'
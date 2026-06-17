from django.db import models
from .base_measurement import BaseMeasurement


class PantsMeasurement(models.Model):
    base   = models.OneToOneField(BaseMeasurement, on_delete=models.CASCADE, related_name='pants')
    length = models.FloatField(null=True, blank=True, verbose_name='Length')

    class Meta:
        verbose_name = 'Pants'
        verbose_name_plural = 'Pants'
from django.db import models
from .base_measurement import BaseMeasurement

from .upper_body import UpperBodyMeasurement, WomenUpperExtra



class BlouseMeasurement(UpperBodyMeasurement, WomenUpperExtra):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='blouse'
    )

    

    neck = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Blouse"
        verbose_name_plural = "Blouses"
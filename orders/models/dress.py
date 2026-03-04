from django.db import models
from .base_measurement import BaseMeasurement
from .upper_body import UpperBodyMeasurement, WomenUpperExtra




class DressMeasurement(UpperBodyMeasurement, WomenUpperExtra):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='dress'
    )

    

    neck = models.FloatField(null=True, blank=True)
    deep_front = models.FloatField(null=True, blank=True)
    deep_back = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Dress"
        verbose_name_plural = "Dresses"


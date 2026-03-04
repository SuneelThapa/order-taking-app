from django.db import models
from .base_measurement import BaseMeasurement
from .upper_body import UpperBodyMeasurement




class ShirtMeasurement(UpperBodyMeasurement):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='shirt'
    )

    

    neck = models.FloatField(null=True, blank=True)
    stomach = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Shirt"
        verbose_name_plural = "Shirts"
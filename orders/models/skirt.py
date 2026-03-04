from django.db import models
from .base_measurement import BaseMeasurement
from .lower_body import LowerBodyMeasurement




class SkirtMeasurement(LowerBodyMeasurement):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='skirt'
    )

    

    class Meta:
        verbose_name = "Skirt"
        verbose_name_plural = "Skirts"
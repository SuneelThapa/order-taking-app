from django.db import models
from .base_measurement import BaseMeasurement
from .upper_body import UpperBodyMeasurement




class VestMeasurement(UpperBodyMeasurement):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='vest'
    )

    

    stomach = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)


    class Meta:
        verbose_name = "Vest"
        verbose_name_plural = "Vests"
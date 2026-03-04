from django.db import models
from .base_measurement import BaseMeasurement
from .upper_body import UpperBodyMeasurement



class JacketMeasurement(UpperBodyMeasurement):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='jacket'
    )
    
    
    
    stomach = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Jacket"
        verbose_name_plural = "Jackets"
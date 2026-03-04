from django.db import models
from .base_measurement import BaseMeasurement
from .upper_body import UpperBodyMeasurement
from .lower_body import LowerBodyMeasurement, PantsExtra



class SuitMeasurement(UpperBodyMeasurement, LowerBodyMeasurement, PantsExtra):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='suit'
    )
    
    
    
    stomach = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Suit"
        verbose_name_plural = "Suits"








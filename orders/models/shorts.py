from django.db import models
from .base_measurement import BaseMeasurement

from .lower_body import LowerBodyMeasurement, PantsExtra



class ShortsMeasurement(LowerBodyMeasurement, PantsExtra):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='shorts'
    )

    

    class Meta:
        verbose_name = "Shorts"
        verbose_name_plural = "Shorts"
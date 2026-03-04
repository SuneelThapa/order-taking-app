from django.db import models
from .base_measurement import BaseMeasurement
from .lower_body import LowerBodyMeasurement, PantsExtra



class PantsMeasurement(LowerBodyMeasurement, PantsExtra):
    base = models.OneToOneField(
        BaseMeasurement,
        on_delete=models.CASCADE,
        related_name='pants'
    )

    

    class Meta:
        verbose_name = "Pants"
        verbose_name_plural = "Pants"
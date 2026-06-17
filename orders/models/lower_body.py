from django.db import models


class LowerBodyMeasurement(models.Model):
    """Kept for import compatibility — fields moved to BodyMeasurement."""
    class Meta:
        abstract = True


class PantsExtra(models.Model):
    """Kept for import compatibility — fields moved to BodyMeasurement."""
    class Meta:
        abstract = True
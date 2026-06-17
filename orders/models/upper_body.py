from django.db import models


class UpperBodyMeasurement(models.Model):
    """Kept for import compatibility — fields moved to BodyMeasurement."""
    class Meta:
        abstract = True


class WomenUpperExtra(models.Model):
    """Kept for import compatibility — fields moved to BodyMeasurement."""
    class Meta:
        abstract = True
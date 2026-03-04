from django.db import models


class LowerBodyMeasurement(models.Model):
    waist = models.FloatField(null=True, blank=True)
    hips = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True


class PantsExtra(models.Model):
    crotch = models.FloatField(null=True, blank=True)
    thigh = models.FloatField(null=True, blank=True)
    knee = models.FloatField(null=True, blank=True)
    cuff = models.FloatField(null=True, blank=True)
    belly = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True
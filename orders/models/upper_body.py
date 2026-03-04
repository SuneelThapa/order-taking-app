from django.db import models


class UpperBodyMeasurement(models.Model):
    shoulder = models.FloatField(null=True, blank=True)
    sleeve = models.FloatField(null=True, blank=True)
    biceps = models.FloatField(null=True, blank=True)
    chest = models.FloatField(null=True, blank=True)
    hips = models.FloatField(null=True, blank=True)
    front = models.FloatField(null=True, blank=True)
    back = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True


class WomenUpperExtra(models.Model):
    high_chest = models.FloatField(null=True, blank=True)
    waist = models.FloatField(null=True, blank=True)
    upper_hips = models.FloatField(null=True, blank=True)

    shoulder_to_middle_breast = models.FloatField(null=True, blank=True)
    shoulder_to_under_breast = models.FloatField(null=True, blank=True)
    middle_breast_to_middle_breast = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True
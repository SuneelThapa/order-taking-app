from django.db import models


class ProductType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    #need to add the exact same class model name here
    measurement_model = models.CharField(max_length=100, help_text="Measurement model class name")

    def __str__(self):
        return self.name
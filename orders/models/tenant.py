from django.db import models
from cloudinary.models import CloudinaryField


class Tenant(models.Model):
    name       = models.CharField(max_length=255)
    subdomain  = models.CharField(max_length=100, unique=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    logo       = CloudinaryField('logo',    blank=True, null=True,
                                 help_text='Shop logo shown in sidebar')
    favicon    = CloudinaryField('favicon', blank=True, null=True,
                                 help_text='Browser tab icon (32x32 recommended)')
    package    = models.CharField(
        max_length=30,
        choices=[
            ('studio',           'Studio only'),
            ('studio_catalogue', 'Studio + Catalogue'),
        ],
        default='studio',
    )

    def __str__(self):
        return self.name
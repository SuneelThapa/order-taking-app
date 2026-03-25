# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from orders.models.tenant import Tenant
from cloudinary.models import CloudinaryField


class CustomUser(AbstractUser):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    can_delete = models.BooleanField(default=False)
    is_tenant = models.BooleanField(default=False)  # tenant/reseller
    profile_image = CloudinaryField('profile image', blank=True, null=True)  # <-- added


    def __str__(self):
        return self.username
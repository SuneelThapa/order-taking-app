import uuid
from django.db import models


class TempPhoto(models.Model):
    """
    Temporarily stores an uploaded photo before the order form is successfully saved.
    Allows images to survive validation errors — uploaded immediately on file select,
    referenced by UUID on subsequent submits.
    Auto-cleaned after 24h via management command or periodic task.
    """
    uuid       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    image      = models.ImageField(upload_to='temp_photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Temp Photo'
        verbose_name_plural = 'Temp Photos'

    def __str__(self):
        return f'TempPhoto {self.uuid}'
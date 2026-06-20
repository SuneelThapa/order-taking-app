import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta


class ScratchPadSession(models.Model):
    MODE_CHOICES = [
        ('contact',      'Contact Info'),
        ('measurements', 'Measurements'),
    ]
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('processed', 'Processed'),
    ]

    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    mode       = models.CharField(max_length=20, choices=MODE_CHOICES)
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result     = models.JSONField(default=dict, blank=True)
    gender     = models.CharField(max_length=10, default='men', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name        = 'Scratch Pad Session'
        verbose_name_plural = 'Scratch Pad Sessions'
        ordering            = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_processed(self):
        return self.status == 'processed'

    def __str__(self):
        return f'{self.get_mode_display()} — {self.status} ({self.token})'
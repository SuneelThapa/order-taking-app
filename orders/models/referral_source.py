from django.db import models


class ReferralSource(models.Model):

    TYPE_CHOICES = [
        ('tuktuk', 'Tuk-Tuk Driver'),
        ('online', 'Online'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Referral Source'
        verbose_name_plural = 'Referral Sources'

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

from django.db import models
from django.conf import settings

from .client import Client


class EmailLog(models.Model):

    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('bounced', 'Bounced'),
        ('failed', 'Failed'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='email_logs',
        db_index=True
    )

    subject = models.CharField(max_length=255)
    body = models.TextField()

    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='emails_sent'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='sent'
    )

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'

    def __str__(self):
        return f"Email to {self.client.name} — {self.subject} ({self.status})"

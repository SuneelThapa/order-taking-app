from django.db import models
from .tenant import Tenant
from .client import Client


class WhatsAppMessage(models.Model):
    DIRECTION_CHOICES = [
        ("in",  "Incoming"),
        ("out", "Outgoing"),
    ]
    STATUS_CHOICES = [
        ("received", "Received"),
        ("sent",     "Sent"),
        ("delivered","Delivered"),
        ("read",     "Read"),
        ("failed",   "Failed"),
    ]

    tenant      = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="whatsapp_messages")
    client      = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="whatsapp_messages")
    direction   = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default="sent")
    from_number = models.CharField(max_length=30)
    to_number   = models.CharField(max_length=30)
    message     = models.TextField()
    wa_message_id = models.CharField(max_length=100, blank=True, default="", db_index=True)
    template_name = models.CharField(max_length=100, blank=True, default="")
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at     = models.DateTimeField(null=True, blank=True)
    read_by     = models.ForeignKey(
        "accounts.CustomUser", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="read_messages"
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "WhatsApp Message"
        verbose_name_plural = "WhatsApp Messages"

    def __str__(self):
        return f"{self.direction} {self.from_number} -> {self.to_number}: {self.message[:50]}"

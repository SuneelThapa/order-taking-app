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
    # WhatsApp API credentials per tenant
    whatsapp_token           = models.TextField(
        blank=True, default='',
        help_text='WhatsApp Business API permanent token'
    )
    whatsapp_phone_number_id = models.CharField(
        max_length=50, blank=True, default='',
        help_text='WhatsApp Phone Number ID from Meta Developer Dashboard'
    )
    # Catalogue
    has_catalogue            = models.BooleanField(
        default=False,
        help_text='Shop has catalogue app enabled'
    )
    catalogue_subdomain      = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Catalogue subdomain e.g. sukhumvit → sukhumvit.catalogue.emporiumarmani.com'
    )

    # Display board
    display_key = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Secret key for status board URL e.g. shop2026'
    )

    def __str__(self):
        return self.name

    @property
    def whatsapp_access_token(self):
        """Return tenant's own token or fall back to system token."""
        from django.conf import settings
        return self.whatsapp_token or getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')

    @property
    def whatsapp_number_id(self):
        """Return tenant's own phone number ID or fall back to system."""
        from django.conf import settings
        return self.whatsapp_phone_number_id or getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
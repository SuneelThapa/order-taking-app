from .base import *

DEBUG = False

ADMINS = [
    ("Sunny Thapa", "latkolat@gmail.com"),
]

ALLOWED_HOSTS = ['*']

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}

STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

CSRF_TRUSTED_ORIGINS = [
    "https://*.emporiumarmani.com",
    "https://studio.emporiumarmani.com",
    "http://143.198.207.146",
]

# -- WhatsApp API --------------------------------------------------
import os
WHATSAPP_ACCESS_TOKEN    = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')

# -- Anthropic API -------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

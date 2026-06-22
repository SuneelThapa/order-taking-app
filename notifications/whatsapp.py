"""
notifications/whatsapp.py
WhatsApp Cloud API wrapper for Emporium Armani order notifications.
Adapted from Mogok Thu Lek Ya whatsapp_bot/api.py
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

WA_API_URL = "https://graph.facebook.com/v19.0/{phone_number_id}/messages"


def _headers():
    return {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _url():
    return WA_API_URL.format(
        phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID
    )


def _post(payload):
    try:
        resp = requests.post(
            _url(), json=payload, headers=_headers(), timeout=10
        )
        if not resp.ok:
            logger.error(
                f"WhatsApp API error {resp.status_code}: {resp.text}"
            )
            return None
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"WhatsApp request failed: {e}")
        return None


def send_text(to, text):
    """Send a plain text WhatsApp message."""
    # Strip + from E.164 format
    to = to.lstrip('+')
    return _post({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    })


# ─────────────────────────────────────────────────────────────
# ORDER NOTIFICATION TEMPLATES
# ─────────────────────────────────────────────────────────────

def notify_order_confirmed(client, order):
    """Sent when order is confirmed/created."""
    if not client.is_eligible_for_notifications:
        return
    msg = (
        f"Hello {client.name}! 👋\n\n"
        f"✅ Your order *#{order.order_number}* has been confirmed at "
        f"*Emporium Armani*.\n\n"
        f"We'll keep you updated on the progress. "
        f"Thank you for choosing us! 🎩"
    )
    return send_text(client.phone, msg)


def notify_order_ready(client, order):
    """Sent when order status changes to 'ready'."""
    if not client.is_eligible_for_notifications:
        return
    msg = (
        f"Hello {client.name}! 🎉\n\n"
        f"Great news! Your order *#{order.order_number}* is *ready*.\n\n"
        f"Please contact us to arrange pickup or delivery.\n\n"
        f"📍 Emporium Armani, Sukhumvit\n"
        f"📱 Reply to this message or call us."
    )
    return send_text(client.phone, msg)


def notify_fitting_reminder(client, order):
    """Sent 1 day before fitting date."""
    if not client.is_eligible_for_notifications:
        return
    fitting_str = order.fitting_date.strftime('%A, %B %d') if order.fitting_date else 'tomorrow'
    if order.fitting_time:
        fitting_str += f' at {order.fitting_time.strftime("%I:%M %p")}'
    msg = (
        f"Hello {client.name}! 👔\n\n"
        f"Friendly reminder — your *fitting appointment* is scheduled for "
        f"*{fitting_str}*.\n\n"
        f"📍 Emporium Armani, Sukhumvit\n\n"
        f"Please reply if you need to reschedule. See you soon!"
    )
    return send_text(client.phone, msg)


def notify_fitting_reminder_3hr(client, order):
    """Sent 3 hours before fitting time."""
    if not client.is_eligible_for_notifications:
        return
    fitting_time = order.fitting_time.strftime('%I:%M %p') if order.fitting_time else 'today'
    msg = (
        f"Hello {client.name}! ⏰\n\n"
        f"Just a reminder — your *fitting appointment* is in *3 hours* at *{fitting_time}*.\n\n"
        f"📍 Emporium Armani, Sukhumvit\n\n"
        f"We look forward to seeing you! Reply if you need to reschedule."
    )
    return send_text(client.phone, msg)


def notify_order_delivered(client, order):
    """Sent when order is delivered."""
    if not client.is_eligible_for_notifications:
        return
    msg = (
        f"Hello {client.name}! 🎩\n\n"
        f"Your order *#{order.order_number}* has been delivered. "
        f"We hope you love it!\n\n"
        f"Thank you for choosing *Emporium Armani*. "
        f"We look forward to serving you again. 🙏"
    )
    return send_text(client.phone, msg)


def notify_return_3_months(client):
    """Sent 3 months after last delivered order."""
    if not client.is_eligible_for_notifications:
        return
    msg = (
        f"Hello {client.name}! 👋\n\n"
        f"It's been a while since your last visit to *Emporium Armani*.\n\n"
        f"Your measurements are saved and ready — "
        f"ordering your next suit has never been easier! 🎩\n\n"
        f"Reply to this message or visit us on Sukhumvit anytime."
    )
    return send_text(client.phone, msg)


def notify_return_6_months(client):
    """Sent 6 months after last delivered order — includes discount."""
    if not client.is_eligible_for_notifications:
        return
    discount = client.loyalty_discount
    tier     = client.loyalty_tier

    if discount > 0:
        offer = (
            f"As a valued *{tier.title()} member*, "
            f"enjoy *{discount}% off* your next order! 🎁"
        )
    else:
        offer = "Come back and enjoy our premium tailoring service! 🎁"

    msg = (
        f"Hello {client.name}! 🎩\n\n"
        f"We miss you at *Emporium Armani*!\n\n"
        f"{offer}\n\n"
        f"Your measurements are still on file — "
        f"just visit us or reply to this message to get started."
    )
    return send_text(client.phone, msg)


def notify_birthday(client):
    """Sent on client's birthday."""
    if not client.is_eligible_for_notifications:
        return
    if not client.birthday:
        return
    discount = max(client.loyalty_discount, 10)  # minimum 10% for birthday
    msg = (
        f"Happy Birthday {client.name}! 🎂🎉\n\n"
        f"*Emporium Armani* wishes you a wonderful birthday!\n\n"
        f"As our gift to you, enjoy *{discount}% off* your next order "
        f"this month. 🎁🎩\n\n"
        f"Reply to this message to book your appointment."
    )
    return send_text(client.phone, msg)
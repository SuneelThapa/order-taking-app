"""
notifications/whatsapp.py
WhatsApp Cloud API wrapper for order notifications.
Supports per-tenant WhatsApp credentials with system fallback.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

WA_API_URL = "https://graph.facebook.com/v19.0/{phone_number_id}/messages"


def _headers(tenant=None):
    token = (tenant.whatsapp_access_token if tenant
             else getattr(settings, 'WHATSAPP_ACCESS_TOKEN', ''))
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _url(tenant=None):
    phone_number_id = (tenant.whatsapp_number_id if tenant
                       else getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', ''))
    return WA_API_URL.format(phone_number_id=phone_number_id)


def _post(payload, tenant=None):
    try:
        resp = requests.post(
            _url(tenant), json=payload, headers=_headers(tenant), timeout=10
        )
        if not resp.ok:
            logger.error(f"WhatsApp API error {resp.status_code}: {resp.text}")
            return None
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"WhatsApp request failed: {e}")
        return None


def send_text(to, text, tenant=None):
    """Send a plain text WhatsApp message."""
    to = to.lstrip('+')
    return _post({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }, tenant=tenant)


def notify_order_confirmed(client, order):
    if not client.is_eligible_for_notifications:
        return
    tenant = order.tenant
    msg = (
        f"Hello {client.name}! Your order *#{order.order_number}* has been confirmed at "
        f"*{tenant.name}*. We'll keep you updated. Thank you for choosing us!"
    )
    return send_text(client.phone, msg, tenant=tenant)


def notify_order_ready(client, order):
    if not client.is_eligible_for_notifications:
        return
    tenant = order.tenant
    msg = (
        f"Hello {client.name}! Your order *#{order.order_number}* is *ready*.\n\n"
        f"Please contact us to arrange pickup or delivery.\n"
        f"📍 {tenant.name}"
    )
    return send_text(client.phone, msg, tenant=tenant)


def notify_fitting_reminder(client, order):
    if not client.is_eligible_for_notifications:
        return
    tenant = order.tenant
    fitting_str = order.fitting_date.strftime('%A, %B %d') if order.fitting_date else 'tomorrow'
    if order.fitting_time:
        fitting_str += f' at {order.fitting_time.strftime("%I:%M %p")}'
    msg = (
        f"Hello {client.name}! Reminder — your *fitting appointment* is on "
        f"*{fitting_str}*.\n\n"
        f"📍 {tenant.name}\n\n"
        f"Please reply if you need to reschedule."
    )
    return send_text(client.phone, msg, tenant=tenant)


def notify_fitting_reminder_3hr(client, order):
    if not client.is_eligible_for_notifications:
        return
    tenant = order.tenant
    fitting_time = order.fitting_time.strftime('%I:%M %p') if order.fitting_time else 'today'
    msg = (
        f"Hello {client.name}! Your *fitting appointment* is in *3 hours* at *{fitting_time}*.\n\n"
        f"📍 {tenant.name}\n\n"
        f"Reply if you need to reschedule."
    )
    return send_text(client.phone, msg, tenant=tenant)


def notify_order_delivered(client, order):
    if not client.is_eligible_for_notifications:
        return
    tenant = order.tenant
    msg = (
        f"Hello {client.name}! Your order *#{order.order_number}* has been delivered.\n\n"
        f"We hope you love it! Thank you for choosing *{tenant.name}*."
    )
    return send_text(client.phone, msg, tenant=tenant)


def notify_return_3_months(client, tenant=None):
    if not client.is_eligible_for_notifications:
        return
    shop_name = tenant.name if tenant else 'our shop'
    msg = (
        f"Hello {client.name}! It's been a while since your last order with *{shop_name}*.\n\n"
        f"Your measurements are safely saved, so ordering your next custom bespoke outfit "
        f"is quick and easy.\n\n"
        f"Simply reply to this message to contact us anytime—we'd be happy to help "
        f"you with your next order!"
    )
    return send_text(client.phone, msg, tenant=tenant)


def notify_return_6_months(client, tenant=None):
    if not client.is_eligible_for_notifications:
        return
    shop_name = tenant.name if tenant else 'our shop'
    discount  = client.loyalty_discount
    tier      = client.loyalty_tier
    offer = (f"🎉 As a valued *{tier.title()} Member*, enjoy *{discount}% off* your next order!"
             if discount > 0 else "🎉 Come back and enjoy our premium tailoring service!")
    msg = (
        f"Hello {client.name}! We hope you're doing well. We miss seeing you at *{shop_name}*!\n\n"
        f"We've prepared a special offer just for our valued customers:\n\n"
        f"{offer}\n\n"
        f"Your measurements are still on file, so simply reply to this message to place "
        f"your next custom order."
    )
    return send_text(client.phone, msg, tenant=tenant)


def notify_birthday(client, tenant=None):
    if not client.is_eligible_for_notifications:
        return
    if not client.birthday:
        return
    shop_name = tenant.name if tenant else 'our shop'
    discount  = max(client.loyalty_discount, 10)
    msg = (
        f"Happy Birthday {client.name}!\n\n"
        f"*{shop_name}* wishes you a wonderful birthday!\n\n"
        f"Enjoy *{discount}% off* your next order this month.\n\n"
        f"Reply to book your appointment."
    )
    return send_text(client.phone, msg, tenant=tenant)
import os
import requests
from django.conf import settings


def _post(payload, tenant=None, client=None, message_text="", template_name=""):
    """Send a WhatsApp message via Cloud API."""
    if tenant:
        token    = tenant.whatsapp_access_token
        phone_id = tenant.whatsapp_number_id
    else:
        token    = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")

    if not token or not phone_id:
        return {"error": "WhatsApp credentials not configured"}

    resp = requests.post(
        f"https://graph.facebook.com/v20.0/{phone_id}/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=10,
    )
    try:
        result = resp.json()
    except Exception:
        return {"error": resp.text}

    # Save outgoing message to database
    try:
        from orders.models import WhatsAppMessage
        to_number = payload.get("to", "")
        wa_msg_id = ""
        if result and "messages" in result:
            wa_msg_id = result["messages"][0].get("id", "")
        WhatsAppMessage.objects.create(
            tenant=tenant,
            client=client,
            direction="out",
            status="sent",
            from_number=phone_id,
            to_number="+" + to_number.lstrip("+"),
            message=message_text,
            wa_message_id=wa_msg_id,
            template_name=template_name,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not save outgoing WhatsApp message: {e}")

    return result


def send_text(to, text, tenant=None):
    """Send a plain text WhatsApp message (only works within 24hr conversation window)."""
    to = to.lstrip("+")
    return _post({
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }, tenant=tenant)


def send_template(to, template_name, language_code="en_US", components=None, tenant=None):
    """Send a pre-approved WhatsApp message template."""
    to = to.lstrip("+")
    payload = {
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "template",
        "template": {
            "name":     template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        payload["template"]["components"] = components
    return _post(payload, tenant=tenant)


def _body_params(*values):
    """Build a body component with positional text parameters."""
    return [{
        "type": "body",
        "parameters": [
            {"type": "text", "text": str(v)} for v in values
        ],
    }]


# ── Order lifecycle notifications ──────────────────────────────────────────────

def notify_order_confirmed(client, order):
    if not client.is_eligible_for_notifications:
        return
    return send_template(
        client.phone,
        "order_confirmed",
        components=_body_params(client.name, order.order_number),
        tenant=getattr(order, "tenant", None),
    )


def notify_order_ready(client, order):
    if not client.is_eligible_for_notifications:
        return
    shop_name = order.tenant.name if order.tenant else "our shop"
    return send_template(
        client.phone,
        "order_ready",
        components=_body_params(client.name, order.order_number, shop_name),
        tenant=getattr(order, "tenant", None),
    )


def notify_fitting_reminder(client, order):
    if not client.is_eligible_for_notifications:
        return
    shop_name   = order.tenant.name if order.tenant else "Emporium Armani"
    fitting_date = str(order.fitting_date) if order.fitting_date else "your scheduled date"
    fitting_time = str(order.fitting_time) if order.fitting_time else "the scheduled time"
    return send_template(
        client.phone,
        "fitting_reminder",
        components=_body_params(client.name, shop_name, fitting_date, fitting_time),
        tenant=getattr(order, "tenant", None),
    )


def notify_fitting_reminder_3hr(client, order):
    if not client.is_eligible_for_notifications:
        return
    return send_template(
        client.phone,
        "fitting_reminder_3hr",
        components=_body_params(client.name, order.order_number),
        tenant=getattr(order, "tenant", None),
    )


def notify_order_delivered(client, order):
    if not client.is_eligible_for_notifications:
        return
    delivery_date = str(order.delivery_date) if order.delivery_date else "today"
    return send_template(
        client.phone,
        "order_delivered",
        components=_body_params(order.order_number, delivery_date),
        tenant=getattr(order, "tenant", None),
    )


# ── Return reminders ───────────────────────────────────────────────────────────

def notify_return_3_months(client, tenant=None):
    if not client.is_eligible_for_notifications:
        return
    shop_name = tenant.name if tenant else "our shop"
    return send_template(
        client.phone,
        "return_3_months",
        components=_body_params(client.name, shop_name),
        tenant=tenant,
    )


def notify_return_6_months(client, tenant=None):
    if not client.is_eligible_for_notifications:
        return
    shop_name = tenant.name if tenant else "our shop"
    discount  = client.loyalty_discount
    tier      = client.loyalty_tier
    offer = (
        f"As a valued {tier.title()} Member, enjoy {discount}% off your next order!"
        if discount > 0
        else "Come back and enjoy our premium tailoring service!"
    )
    return send_template(
        client.phone,
        "return_6_months",
        components=_body_params(client.name, shop_name, offer),
        tenant=tenant,
    )


# ── Birthday ───────────────────────────────────────────────────────────────────

def notify_birthday(client, tenant=None):
    if not client.is_eligible_for_notifications:
        return
    shop_name = tenant.name if tenant else "our shop"
    return send_template(
        client.phone,
        "birthday_greeting",
        components=_body_params(client.name, shop_name),
        tenant=tenant,
    )

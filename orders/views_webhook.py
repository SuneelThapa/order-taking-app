import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from orders.models import Tenant, Client, WhatsAppMessage

logger = logging.getLogger(__name__)

VERIFY_TOKEN = "tailorstudio_webhook_2026"


@csrf_exempt
def whatsapp_webhook(request):
    if request.method == "GET":
        mode      = request.GET.get("hub.mode")
        token     = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Forbidden", status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            _process_webhook(data)
        except Exception as e:
            logger.error(f"Webhook error: {e}")
        return JsonResponse({"status": "ok"})

    return HttpResponse(status=405)


def _process_webhook(data):
    for entry in data.get("entry", []):
        waba_id = entry.get("id")
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                _handle_incoming_message(msg, waba_id, value)

            # Handle status updates
            statuses = value.get("statuses", [])
            for status in statuses:
                _handle_status_update(status)


def _handle_incoming_message(msg, waba_id, value):
    from_number = msg.get("from", "")
    wa_msg_id   = msg.get("id", "")
    msg_type    = msg.get("type", "text")
    timestamp   = msg.get("timestamp")

    # Extract text
    if msg_type == "text":
        text = msg.get("text", {}).get("body", "")
    elif msg_type == "image":
        text = "[Image]"
    elif msg_type == "document":
        text = "[Document]"
    elif msg_type == "audio":
        text = "[Audio message]"
    else:
        text = f"[{msg_type}]"

    # Find tenant by WABA ID
    tenant = None
    try:
        tenant = Tenant.objects.get(
            whatsapp_phone_number_id__isnull=False
        )
    except Tenant.MultipleObjectsReturned:
        pass
    except Tenant.DoesNotExist:
        pass

    # Try to find tenant more specifically
    phone_id = value.get("metadata", {}).get("phone_number_id", "")
    if phone_id:
        try:
            tenant = Tenant.objects.get(whatsapp_phone_number_id=phone_id)
        except Exception:
            pass

    if not tenant:
        logger.warning(f"No tenant found for webhook message from {from_number}")
        return

    # Find client by phone number
    clean_phone = "+" + from_number.lstrip("+")
    client = Client.objects.filter(
        tenant=tenant,
        phone=clean_phone
    ).first()

    # Save message
    WhatsAppMessage.objects.create(
        tenant=tenant,
        client=client,
        direction="in",
        status="received",
        from_number=clean_phone,
        to_number=value.get("metadata", {}).get("display_phone_number", ""),
        message=text,
        wa_message_id=wa_msg_id,
    )
    logger.info(f"Saved incoming WhatsApp from {clean_phone}: {text[:50]}")


def _handle_status_update(status):
    wa_msg_id  = status.get("id", "")
    new_status = status.get("status", "")
    if not wa_msg_id or not new_status:
        return
    WhatsAppMessage.objects.filter(
        wa_message_id=wa_msg_id
    ).update(status=new_status)

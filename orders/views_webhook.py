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
            body = request.body
            logger.info(f"Webhook POST received: {body[:500]}")
            data = json.loads(body)
            logger.info(f"Webhook data keys: {list(data.keys())}")
            _process_webhook(data)
        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
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


def _fetch_media_url(media_id, tenant):
    """Fetch media download URL from WhatsApp API."""
    if not media_id or not tenant:
        return ""
    try:
        import requests
        resp = requests.get(
            f"https://graph.facebook.com/v20.0/{media_id}",
            headers={"Authorization": f"Bearer {tenant.whatsapp_access_token}"},
            timeout=10
        )
        data = resp.json()
        media_url = data.get("url", "")
        if not media_url:
            return ""
        # Download and upload to Cloudinary for permanent storage
        img_resp = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {tenant.whatsapp_access_token}"},
            timeout=30
        )
        if img_resp.status_code == 200:
            import cloudinary.uploader
            from io import BytesIO
            result = cloudinary.uploader.upload(
                BytesIO(img_resp.content),
                folder="whatsapp_received",
                resource_type="auto"
            )
            return result.get("secure_url", "")
    except Exception as e:
        logger.error(f"Failed to fetch media: {e}")
    return ""


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

    # Find tenant by phone_number_id from webhook metadata
    phone_id = value.get("metadata", {}).get("phone_number_id", "")
    tenant = None

    if phone_id:
        try:
            tenant = Tenant.objects.get(whatsapp_phone_number_id=phone_id, is_active=True)
        except Tenant.DoesNotExist:
            pass
        except Tenant.MultipleObjectsReturned:
            tenant = Tenant.objects.filter(whatsapp_phone_number_id=phone_id, is_active=True).first()

    # Fallback: use first active tenant with WhatsApp configured
    if not tenant:
        tenant = Tenant.objects.filter(
            whatsapp_phone_number_id__isnull=False,
            is_active=True
        ).exclude(whatsapp_phone_number_id="").first()

    if not tenant:
        logger.warning(f"No tenant found for webhook message from {from_number} (phone_id={phone_id})")
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
        media_url=media_url,
        media_type=media_type,
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

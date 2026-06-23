# orders/views.py
import base64
import json
import uuid
from datetime import date as _date, timedelta as _timedelta
from urllib.parse import quote as _quote

from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import HttpResponse
from django.apps import apps
from django.forms import modelform_factory

from .models import (
    Order, Client, ProductType, BaseMeasurement,
    OrderItemPhoto, ScratchNote, Delivery, Payment,
    OrderStaff, ClientSignature, CancellationRecord,
    OrderItem, TargetItem, VariationType, VariationOption,
    FabricZone, ProductionBill, FabricSet,
    FabricZoneEntry, BillStyleSelection, Monogram,
    BodyMeasurement, ClientPhoto, TempPhoto,
)
from .forms import (
    ClientForm, OrderForm, OrderItemFormSet,
    DeliveryForm,
    PaymentForm, PaymentCreateFormSet,
    OrderStaffFormSet, get_measurement_form,
    CancellationForm,
    ClientEditForm,
    BodyMeasurementForm,
)


def staff_check(user):
    return user.is_staff


# ─────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────
def _get_counts(tenant):
    key = f"order_status_counts_{tenant.id}"
    counts = cache.get(key)
    if counts is None:
        counts = {
            "new":        Order.objects.filter(status="new",        tenant=tenant).count(),
            "pending":    Order.objects.filter(status="pending",    tenant=tenant).count(),
            "processing": Order.objects.filter(status="processing", tenant=tenant).count(),
            "ready":      Order.objects.filter(status="ready",      tenant=tenant).count(),
            "delivered":  Order.objects.filter(status="delivered",  tenant=tenant).count(),
        }
        cache.set(key, counts, 60)
    return counts


def _build_cards(counts):
    return [
        {"status": "new",        "label": "New",        "css": "c-new",       "icon": "bi-inbox",           "count": counts["new"]},
        {"status": "pending",    "label": "Pending",    "css": "c-pending",   "icon": "bi-hourglass-split", "count": counts["pending"]},
        {"status": "processing", "label": "Processing", "css": "c-progress",  "icon": "bi-gear",            "count": counts["processing"]},
        {"status": "ready",      "label": "Ready",      "css": "c-ready",     "icon": "bi-check2-circle",   "count": counts["ready"]},
        {"status": "delivered",  "label": "Delivered",  "css": "c-delivered", "icon": "bi-truck",           "count": counts["delivered"]},
    ]


_ALLOWED_SORTS = {
    "order_number", "-order_number", "status", "-status",
    "total_amount", "-total_amount", "created_at", "-created_at",
}


def _orders_table_context(request, tenant):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    status     = request.GET.get("status")    or ""
    q          = (request.GET.get("q") or "").strip()
    sort       = request.GET.get("sort")      or "-created_at"
    from_date  = request.GET.get("from_date") or ""
    to_date    = request.GET.get("to_date")   or ""
    staff_id   = request.GET.get("staff_id")  or ""
    urgent     = request.GET.get("urgent")    or ""
    min_amount = request.GET.get("min_amount") or ""
    max_amount = request.GET.get("max_amount") or ""

    if sort not in _ALLOWED_SORTS:
        sort = "-created_at"
    page = request.GET.get("page", 1)

    orders = Order.objects.filter(tenant=tenant).select_related("client", "delivery")

    if status:
        orders = orders.filter(status=status)
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q)
            | Q(client__name__icontains=q)
            | Q(client__phone__icontains=q)
            | Q(client__email__icontains=q)
            | Q(hotel_name__icontains=q)
        )
    if from_date:
        orders = orders.filter(created_at__date__gte=from_date)
    if to_date:
        orders = orders.filter(created_at__date__lte=to_date)
    if staff_id:
        orders = orders.filter(staff_assignments__user_id=staff_id).distinct()
    if urgent:
        orders = orders.filter(is_urgent=True)
    if min_amount:
        try:    orders = orders.filter(total_amount__gte=float(min_amount))
        except: pass
    if max_amount:
        try:    orders = orders.filter(total_amount__lte=float(max_amount))
        except: pass

    staff_users = User.objects.filter(
        staff_profile__isnull=False
    ).order_by("first_name", "last_name", "username")

    has_filters = any([status, q, from_date, to_date, staff_id, urgent,
                       min_amount, max_amount])

    paginator = Paginator(orders.order_by(sort), 10)
    return {
        "page_obj":          paginator.get_page(page),
        "current_status":    status,
        "current_sort":      sort,
        "current_q":         q,
        "current_from":      from_date,
        "current_to":        to_date,
        "current_staff":     staff_id,
        "current_urgent":    urgent,
        "current_min_amount": min_amount,
        "current_max_amount": max_amount,
        "staff_users":       staff_users,
        "has_filters":       has_filters,
    }


# ─────────────────────────────────────────────────────────
# Dashboard / cards / table / detail / delete
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def dashboard(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    pending_refunds = CancellationRecord.objects.filter(
        resolution="partial_refund",
        approved_by=None,
        order__tenant=tenant,
    ).select_related("order__client", "canceled_by").order_by("-order__created_at")
    return render(request, "admin_dashboard/dashboard.html", {
        "cards":           _build_cards(_get_counts(tenant)),
        "pending_refunds": pending_refunds,
    })


@user_passes_test(staff_check)
def stat_cards(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    return render(request, "admin_dashboard/partials/_stat_cards.html",
                  {"cards": _build_cards(_get_counts(tenant))})


@user_passes_test(staff_check)
def orders_table(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    return render(request, "admin_dashboard/partials/orders_table.html",
                  _orders_table_context(request, tenant))


@user_passes_test(staff_check)
def order_detail(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    order = get_object_or_404(
        Order.objects
        .select_related("client", "delivery", "tenant")
        .filter(tenant=tenant),
        pk=pk,
    )

    items_with_measurements = []
    try:
        for item in order.items.select_related("product_type").all():
            try:
                photos = [p for p in item.photos.all() if p.image and p.image.name]
            except Exception:
                photos = []
            items_with_measurements.append({
                "item":   item,
                "photos": photos,
                "fields": _get_measurement_fields(item),
            })
    except Exception as _items_err:
        print(f"DEBUG order_detail items error: {_items_err}")

    try:
        signature = order.signature
    except Exception:
        signature = None

    try:
        payments = list(order.payments.select_related("recorded_by").all())
    except Exception as _e:
        payments = []

    context = {
        "order":                   order,
        "items_with_measurements": items_with_measurements,
        "payments":                payments,
        "signature":               signature,
        "status_choices":          Order.STATUS_CHOICES,
        "quick_pay_form":          PaymentForm(prefix="qp"),
    }
    return render(request, "orders/partials/_order_detail_modal.html", context)


@user_passes_test(staff_check)
def order_delete(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    if request.method != "DELETE":
        return HttpResponse(status=405)

    # Only owner / manager / superuser may delete orders
    try:
        user_role = request.user.staff_profile.role
    except Exception:
        user_role = "owner" if request.user.is_superuser else "staff"

    if user_role not in ("owner", "manager") and not request.user.is_superuser:
        return HttpResponse(
            '<div class="alert alert-danger m-3">'
            '<i class="bi bi-shield-lock me-2"></i>'
            'Only owner or manager can delete orders.'
            '</div>',
            status=403,
        )

    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    order.delete()
    cache.delete(f"order_status_counts_{tenant.id}")
    ctx = _orders_table_context(request, tenant)
    ctx["oob_cards"] = True
    ctx["cards"] = _build_cards(_get_counts(tenant))
    return render(request, "admin_dashboard/partials/orders_table.html", ctx)


# ─────────────────────────────────────────────────────────
# Client search & inline create
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def client_search(request):
    q = (request.GET.get("q") or "").strip()
    clients = []
    if len(q) >= 2:
        clients = Client.objects.filter(
            Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q),
            is_active=True
        ).order_by("name")[:10]
    return render(request, "orders/partials/_client_results.html",
                  {"clients": clients, "q": q})


@user_passes_test(staff_check)
def client_create_inline(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    form = ClientForm(request.POST)
    if form.is_valid():
        client = form.save()
        response = render(request, "orders/partials/_client_card.html", {"client": client})
        response["HX-Trigger"] = json.dumps({
            "clientSelected": {
                "id":    client.pk,
                "name":  client.name,
                "phone": client.phone or "",
            }
        })
        response["X-Created-Client-Id"]    = str(client.pk)
        response["X-Created-Client-Name"]  = client.name
        response["X-Created-Client-Phone"] = client.phone or ""
        return response
    return render(request, "orders/partials/_client_create_form.html", {"client_form": form})


# ─────────────────────────────────────────────────────────
# Payment row
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def payment_row(request):
    try:
        index = int(request.GET.get("index", 0))
    except (TypeError, ValueError):
        index = 0
    form = PaymentForm(prefix=f"payments-{index}")
    return render(request, "orders/partials/_payment_row.html", {"form": form, "index": index})


# ─────────────────────────────────────────────────────────
# Order form — 6-step wizard
# ─────────────────────────────────────────────────────────
WIZARD_STEPS = [
    (1, "Client"),
    (2, "Order"),
    (3, "Items"),
    (4, "Photos & notes"),
    (5, "Logistics"),
    (6, "Finish"),
]


@user_passes_test(staff_check)
def order_form_view(request, pk=None):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    is_edit   = pk is not None
    edit_order = get_object_or_404(Order, pk=pk, tenant=tenant) if is_edit else None

    # Resolve user role once — used for permissions throughout the view
    try:
        user_role = request.user.staff_profile.role
    except Exception:
        user_role = "owner" if request.user.is_superuser else "staff"

    if edit_order and edit_order.status == "canceled":
        messages.error(request, f"Order #{edit_order.order_number} is canceled and cannot be edited.")
        return redirect("orders:dashboard")
    existing_delivery = getattr(edit_order, "delivery", None) if edit_order else None

    if request.method == "POST":
        order_form           = OrderForm(request.POST, instance=edit_order,
                                         user=request.user, tenant=tenant)
        item_formset         = OrderItemFormSet(request.POST, request.FILES, instance=edit_order)
        staff_formset        = OrderStaffFormSet(request.POST, instance=edit_order, prefix="staff")
        delivery_form        = DeliveryForm(request.POST, instance=existing_delivery, prefix="delivery")
        payment_formset      = PaymentCreateFormSet(request.POST, prefix="payments")

        client_id = request.POST.get("client", "").strip()
        client_obj = None
        client_error = None
        if client_id:
            try:
                client_obj = Client.objects.get(pk=client_id)
            except (Client.DoesNotExist, ValueError):
                client_error = "The selected client is invalid. Please search and select again."
        else:
            client_error = "Please select a client before saving."

        core_valid = (
            client_obj is not None
            and order_form.is_valid()
            and item_formset.is_valid()
            and staff_formset.is_valid()
        )
        delivery_valid = delivery_form.is_valid()
        payment_formset.is_valid()
        all_valid = core_valid

        if all_valid:
            order        = order_form.save(commit=False)
            order.tenant = tenant
            order.client = client_obj

            default_status = Order._meta.get_field("status").get_default()
            if getattr(request.user, "is_tenant", False) and request.user.is_staff:
                order.status = order_form.cleaned_data.get("status_hidden") or default_status
            elif getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                order.status = default_status

            if not is_edit:
                order.total_amount = 0
            order.save()
            cache.delete(f"order_status_counts_{tenant.id}")

            if delivery_valid:
                delivery       = delivery_form.save(commit=False)
                delivery.order = order
                delivery.save()

            canvas_data = request.POST.get("scratch_canvas_image")
            if canvas_data:
                try:
                    fmt, imgstr = canvas_data.split(";base64,")
                    ext  = fmt.split("/")[-1]
                    file = ContentFile(base64.b64decode(imgstr),
                                       name=f"scratch_{uuid.uuid4()}.{ext}")
                    ScratchNote.objects.create(order=order, image=file)
                except Exception:
                    pass

            # ── Client photos — multi-person ──────────────────
            person_count = int(request.POST.get('person_count', 1))
            photo_types  = ['front', 'side', 'back']
            for pnum in range(1, person_count + 1):
                for ptype in photo_types:
                    del_key  = f'delete_person_{pnum}_{ptype}'
                    file_key = f'person_{pnum}_{ptype}'
                    temp_key = f'temp_person_{pnum}_{ptype}'
                    if request.POST.get(del_key):
                        ClientPhoto.objects.filter(
                            order=order,
                            person_number=pnum,
                            photo_type=ptype,
                        ).delete()
                    if file_key in request.FILES:
                        # Fresh upload takes priority
                        existing = ClientPhoto.objects.filter(
                            order=order, person_number=pnum, photo_type=ptype,
                        ).first()
                        if existing:
                            existing.image = request.FILES[file_key]
                            existing.save()
                        else:
                            ClientPhoto.objects.create(
                                order=order, person_number=pnum,
                                photo_type=ptype,
                                image=request.FILES[file_key],
                            )
                    elif request.POST.get(temp_key):
                        # Use pre-uploaded temp photo if no fresh file
                        try:
                            temp = TempPhoto.objects.get(uuid=request.POST[temp_key])
                            existing = ClientPhoto.objects.filter(
                                order=order, person_number=pnum, photo_type=ptype,
                            ).first()
                            if existing:
                                existing.image = temp.image
                                existing.save()
                            else:
                                ClientPhoto.objects.create(
                                    order=order, person_number=pnum,
                                    photo_type=ptype, image=temp.image,
                                )
                            temp.delete()
                        except TempPhoto.DoesNotExist:
                            pass

            item_formset.instance = order
            item_formset.save(commit=False)
            total = 0
            for form in item_formset.forms:
                if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                    continue
                item = form.save(commit=False)
                item.order = order
                item.save()
                total += getattr(item, "total_price", 0)

                # Body measurement — save per item
                body_inst = BodyMeasurement.objects.filter(order_item=item).first()
                body_form = BodyMeasurementForm(
                    request.POST,
                    instance=body_inst,
                    prefix=f"body-{form.prefix}",
                )
                if body_form.is_valid():
                    bm = body_form.save(commit=False)
                    bm.order_item = item
                    # Fallback gender to 'men' if not submitted
                    if not bm.gender:
                        bm.gender = 'men'
                    bm.save()

                for uploaded in request.FILES.getlist(f"item_photos_{form.prefix}"):
                    OrderItemPhoto.objects.create(order_item=item, image=uploaded)
                # Also process any temp-uploaded item photos
                idx = 0
                while True:
                    temp_uuid = request.POST.get(f"temp_item_photo_{form.prefix}_{idx}")
                    if not temp_uuid:
                        break
                    try:
                        tmp = TempPhoto.objects.get(uuid=temp_uuid)
                        OrderItemPhoto.objects.create(order_item=item, image=tmp.image)
                        tmp.delete()
                    except TempPhoto.DoesNotExist:
                        pass
                    idx += 1
                for del_id in request.POST.getlist(f"delete_item_photos_{form.prefix}"):
                    OrderItemPhoto.objects.filter(id=del_id, order_item=item).delete()

                if item.product_type_id:
                    model  = apps.get_model("orders", item.product_type.measurement_model)
                    base, _ = BaseMeasurement.objects.get_or_create(order_item=item)
                    MForm  = modelform_factory(model, exclude=("base",))
                    m_inst = model.objects.filter(base=base).first()
                    mform  = MForm(request.POST, instance=m_inst, prefix=f"measure-{form.prefix}")
                    if mform.is_valid():
                        m = mform.save(commit=False)
                        m.base = base
                        m.save()

            for form in item_formset.deleted_forms:
                if form.instance.pk:
                    form.instance.delete()

            manual_total = order_form.cleaned_data.get("total_amount")
            order.total_amount = manual_total if manual_total else total
            order.save()

            staff_formset.instance = order
            for form in staff_formset.forms:
                if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                    continue
                try:
                    assignment       = form.save(commit=False)
                    assignment.order = order
                    try:
                        assignment.commission_percentage = (
                            assignment.user.staff_profile.default_commission_percentage
                        )
                    except Exception:
                        assignment.commission_percentage = 0
                    assignment.save()
                except Exception as _staff_err:
                    print(f"DEBUG: Staff save ERROR: {type(_staff_err).__name__}: {_staff_err}")
            for form in staff_formset.deleted_forms:
                if form.instance.pk:
                    form.instance.delete()

            for form in payment_formset.forms:
                cd = getattr(form, 'cleaned_data', None)
                if not cd or cd.get("DELETE"):
                    continue
                amount = cd.get("original_amount")
                if not amount:
                    continue
                try:
                    payment = Payment(
                        order                = order,
                        recorded_by          = request.user,
                        original_amount      = amount,
                        currency             = cd.get("currency") or "THB",
                        exchange_rate_to_thb = cd.get("exchange_rate_to_thb") or 1,
                        method               = cd.get("method") or request.POST.get(f"{form.prefix}-method", "cash"),
                        type                 = cd.get("type") or request.POST.get(f"{form.prefix}-type", "deposit"),
                        notes                = cd.get("notes") or "",
                    )
                    payment.save()
                except Exception as _pay_err:
                    print(f"DEBUG payment ERROR: {type(_pay_err).__name__}: {_pay_err}")

            sig_data = request.POST.get("signature_canvas_image")
            if sig_data:
                try:
                    fmt, imgstr = sig_data.split(";base64,")
                    ext  = fmt.split("/")[-1]
                    file = ContentFile(base64.b64decode(imgstr),
                                       name=f"sig_{uuid.uuid4()}.{ext}")
                    sig, _ = ClientSignature.objects.get_or_create(order=order)
                    sig.image      = file
                    sig.ip_address = request.META.get("REMOTE_ADDR")
                    sig.save()
                except Exception:
                    pass

            messages.success(request, f"Order #{order.order_number} saved.")
            return redirect("orders:dashboard")

    else:
        client_error = None
        initial = {}
        if not is_edit:
            initial["status_hidden"] = Order._meta.get_field("status").get_default()
        order_form           = OrderForm(instance=edit_order, user=request.user,
                                         tenant=tenant, initial=initial)
        item_formset         = OrderItemFormSet(instance=edit_order)
        staff_formset        = OrderStaffFormSet(instance=edit_order, prefix="staff")
        delivery_form        = DeliveryForm(instance=existing_delivery, prefix="delivery")
        payment_formset      = PaymentCreateFormSet(prefix="payments")

    post = request.POST if request.method == "POST" else None

    # Scratch note + signature canvas — restore on POST error
    scratch_canvas_data   = request.POST.get('scratch_canvas_image',   '') if request.method == 'POST' else ''
    signature_canvas_data = request.POST.get('signature_canvas_image', '') if request.method == 'POST' else ''

    # Temp item photos — collect for re-render on error
    temp_item_photos = {}  # prefix → [{'uuid':..,'url':..}, ...]
    if request.method == 'POST':
        for key, val in request.POST.items():
            if key.startswith('temp_item_photo_'):
                # key format: temp_item_photo_items-N_M
                parts = key[len('temp_item_photo_'):]
                # parts = 'items-N_M', prefix = 'items-N'
                idx = parts.rfind('_')
                if idx >= 0:
                    prefix = parts[:idx]
                    try:
                        tmp = TempPhoto.objects.get(uuid=val)
                        temp_item_photos.setdefault(prefix, []).append(
                            {'uuid': val, 'url': tmp.image.url}
                        )
                    except TempPhoto.DoesNotExist:
                        pass

    # Lock total_amount + currency for EVERYONE when locked
    # Even owners must unlock first — prevents accidental edits
    amount_locked = bool(edit_order and edit_order.total_locked)
    can_lock = user_role in ("owner", "manager") or request.user.is_superuser
    if amount_locked:
        order_form.fields["total_amount"].disabled  = True
        order_form.fields["total_currency"].disabled = True
        if can_lock:
            order_form.fields["total_amount"].help_text = "🔒 Locked — click Unlock below to edit"
        else:
            order_form.fields["total_amount"].help_text = "🔒 Locked — contact owner/manager to unlock"

    item_rows = []
    for form in item_formset.forms:
        item = form.instance
        existing_photos  = list(item.photos.all()) if item.pk else []
        measurement_form = None
        # For saved items — load from DB instance
        if item.pk and item.product_type_id:
            model  = apps.get_model("orders", item.product_type.measurement_model)
            base   = BaseMeasurement.objects.filter(order_item=item).first()
            m_inst = model.objects.filter(base=base).first() if base else None
            MForm  = modelform_factory(model, exclude=("base",))
            measurement_form = MForm(post, instance=m_inst, prefix=f"measure-{form.prefix}")
        # For new items on POST error — load from product_type in POST data
        elif post and not item.pk:
            pt_id = post.get(f"{form.prefix}-product_type", "").strip()
            if pt_id:
                try:
                    pt = ProductType.objects.get(pk=pt_id)
                    model = apps.get_model("orders", pt.measurement_model)
                    MForm = modelform_factory(model, exclude=("base",))
                    measurement_form = MForm(post, prefix=f"measure-{form.prefix}")
                except (ProductType.DoesNotExist, LookupError):
                    pass
        # Load existing body measurement
        body_inst = BodyMeasurement.objects.filter(order_item=item).first() if item.pk else None
        body_form_inst = BodyMeasurementForm(
            post,
            instance=body_inst,
            prefix=f"body-{form.prefix}",
        )
        item_rows.append({
            "form":             form,
            "measurement_form": measurement_form,
            "existing_photos":  existing_photos,
            "body_form":        body_form_inst,
            "temp_photos":      temp_item_photos.get(form.prefix, []),
        })

    selected_client = None
    if edit_order:
        selected_client = edit_order.client
    elif request.method == "POST":
        cid = request.POST.get("client")
        if cid:
            selected_client = Client.objects.filter(pk=cid).first()

    # ── Pre-fill from catalogue inquiry (Convert button) ──────────
    inquiry_prefill = None
    if not is_edit and request.method == "GET":
        inq_name    = request.GET.get("name", "").strip()
        inq_phone   = request.GET.get("phone", "").strip()
        inq_message = request.GET.get("message", "").strip()
        inq_id      = request.GET.get("inquiry", "").strip()
        if inq_name or inq_phone:
            inquiry_prefill = {
                "id":      inq_id,
                "name":    inq_name,
                "phone":   inq_phone,
                "message": inq_message,
            }
            # Try to find existing client by phone
            if inq_phone and not selected_client:
                selected_client = Client.objects.filter(
                    phone__icontains=inq_phone.replace("+", "").strip()
                ).first()

    first_error_step = None
    if request.method == "POST":
        if client_error:
            first_error_step = 1
        elif order_form.errors:
            first_error_step = 2
        elif any(item_formset.errors) or item_formset.non_form_errors():
            first_error_step = 3
        elif any(f.errors for f in client_photo_formset.forms):
            first_error_step = 4
        elif delivery_form.errors:
            first_error_step = 5

    try:
        user_role = request.user.staff_profile.role
    except Exception:
        user_role = "owner" if request.user.is_superuser else "staff"
    can_edit_staff = (not is_edit) or (user_role in ("owner", "manager"))

    # Group existing client photos by person_number for template
    from collections import defaultdict

    class _TempProxy:
        """Wraps a TempPhoto to look like a ClientPhoto for template use."""
        is_temp = True
        def __init__(self, uuid_str, url):
            self.temp_uuid = uuid_str
            class _Img:
                def __init__(self, u): self.url = u
            self.image = _Img(url)

    grouped_photos = defaultdict(dict)
    if edit_order:
        for photo in edit_order.client_photos.order_by('person_number', 'photo_type'):
            grouped_photos[photo.person_number][photo.photo_type] = photo

    # On POST, honour person_count from form (may be more than saved)
    post_person_count = int(request.POST.get('person_count', 1)) if request.method == 'POST' else 1
    initial_persons = max(
        max(grouped_photos.keys()) if grouped_photos else 1,
        post_person_count,
    )

    persons_photos = [
        {
            'num':   pnum,
            'front': grouped_photos[pnum].get('front'),
            'side':  grouped_photos[pnum].get('side'),
            'back':  grouped_photos[pnum].get('back'),
        }
        for pnum in range(1, initial_persons + 1)
    ]

    # On POST with validation errors — supplement with temp-uploaded photos
    if request.method == 'POST':
        for p in persons_photos:
            pnum = p['num']
            for ptype in ('front', 'side', 'back'):
                if p.get(ptype):
                    continue  # Real photo already there
                uuid_str = request.POST.get(f'temp_person_{pnum}_{ptype}')
                if uuid_str:
                    try:
                        tmp = TempPhoto.objects.get(uuid=uuid_str)
                        p[ptype] = _TempProxy(uuid_str, tmp.image.url)
                    except TempPhoto.DoesNotExist:
                        pass

    context = {
        "is_edit":              is_edit,
        "edit_order":           edit_order,
        "order_form":           order_form,
        "amount_locked":        amount_locked,
        "can_lock":             can_lock,
        "can_edit_staff":       can_edit_staff,
        "item_formset":         item_formset,
        "item_rows":            item_rows,
        "persons_photos":       persons_photos,
        "initial_persons":      initial_persons,
        "scratch_canvas_data":   scratch_canvas_data,
        "signature_canvas_data": signature_canvas_data,
        "temp_item_photos":     temp_item_photos,
        "staff_formset":        staff_formset,
        "delivery_form":        delivery_form,
        "payment_formset":      payment_formset,
        "selected_client":      selected_client,
        "client_error":         client_error,
        "steps":                WIZARD_STEPS,
        "client_form_empty":    ClientForm(),
        "first_error_step":     first_error_step,
        "existing_payments":    list(edit_order.payments.select_related("recorded_by").all()) if edit_order else [],
        "existing_signature":   getattr(edit_order, "signature", None) if edit_order else None,
        "inquiry_prefill":      inquiry_prefill,
        "product_type_model_map": {
            str(pt.pk): pt.measurement_model
            for pt in ProductType.objects.all()
        },
    }
    return render(request, "orders/order_form.html", context)


# ─────────────────────────────────────────────────────────
# Blank item row
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_item_row(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    try:
        index = int(request.GET.get("index", 0))
    except (TypeError, ValueError):
        index = 0
    from .forms import OrderItemForm
    form = OrderItemForm(prefix=f"items-{index}")
    return render(request, "orders/partials/_order_item_row.html", {
        "item_form":        form,
        "measurement_form": None,
        "existing_photos":  [],
        "is_new":           True,
        "body_form":        BodyMeasurementForm(prefix=f"body-items-{index}"),
    })


# ─────────────────────────────────────────────────────────
# Load measurement form
# ─────────────────────────────────────────────────────────
def load_measurement_form(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    product_type_id = request.GET.get("product_type")
    prefix          = request.GET.get("prefix")
    if not product_type_id and prefix:
        product_type_id = request.GET.get(f"{prefix}-product_type")
    if not product_type_id or not prefix:
        return HttpResponse("")

    cache_key    = f"product_type_{product_type_id}"
    product_type = cache.get(cache_key)
    if not product_type:
        product_type = get_object_or_404(ProductType, id=product_type_id)
        cache.set(cache_key, product_type, 300)

    MeasurementForm = get_measurement_form(product_type)
    if not MeasurementForm:
        return HttpResponse("")

    form = MeasurementForm(prefix=f"measure-{prefix}")
    return render(request, "admin_dashboard/partials/_dynamic_measurement.html",
                  {"form": form, "product_type": product_type})


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
# Fields that live on BodyMeasurement (to avoid duplication in garment section)
BODY_FIELD_NAMES = frozenset([
    # Universal
    'neck', 'shoulder', 'sleeve', 'biceps', 'chest', 'stomach',
    'hips', 'height', 'weight',
    # Men upper
    'length', 'front', 'back',
    # Men lower
    'pants_waist', 'pants_hip', 'belly', 'crotch', 'thigh', 'knee', 'cuff', 'pants_length',
    # Men posture/desc
    'shoulder_posture', 'stomach_description', 'chest_description',
    # Ladies
    'high_chest', 'upper_hips', 'deep_front', 'deep_back',
    'shoulder_to_middle_breast', 'shoulder_to_under_breast',
    'middle_breast_to_middle_breast',
    'shoulder_to_back', 'shoulder_to_waist',
])

BODY_FIELD_ORDER_MEN = [
    # Upper body
    'neck', 'shoulder', 'sleeve', 'biceps',
    'chest', 'stomach', 'hips', 'length', 'front', 'back',
    # Lower body
    'pants_waist', 'pants_hip', 'belly', 'crotch',
    'thigh', 'knee', 'cuff', 'pants_length',
    # General + posture
    'height', 'weight',
    'shoulder_posture', 'stomach_description', 'chest_description',
]

BODY_FIELD_ORDER_LADIES = [
    'neck', 'shoulder', 'sleeve', 'biceps',
    'high_chest', 'chest', 'upper_hips', 'hips', 'stomach',
    'deep_front', 'deep_back',
    'shoulder_to_middle_breast', 'shoulder_to_under_breast',
    'middle_breast_to_middle_breast',
    'shoulder_to_back', 'shoulder_to_waist',
    'height', 'weight',
]

# Body fields relevant per garment type — only shows fields NOT in garment-specific
# Order: top to bottom as a tailor would measure
GARMENT_BODY_FIELDS = {
    'JacketMeasurement': [
        'shoulder', 'sleeve', 'biceps', 'chest', 'stomach',
        'hips', 'length', 'front', 'back',
        'height', 'weight',
        'shoulder_posture', 'stomach_description', 'chest_description',
    ],
    'ShirtMeasurement': [
        'neck', 'shoulder', 'sleeve', 'biceps', 'chest', 'stomach',
        'hips', 'length', 'front', 'back',
        'height', 'weight',
        'shoulder_posture', 'stomach_description', 'chest_description',
    ],
    'VestMeasurement': [
        'shoulder', 'sleeve', 'biceps', 'chest', 'stomach',
        'hips', 'length', 'front', 'back',
        'height', 'weight',
        'shoulder_posture', 'stomach_description', 'chest_description',
    ],
    'CoatMeasurement': [
        'shoulder', 'sleeve', 'biceps', 'chest', 'stomach',
        'hips', 'length', 'front', 'back',
        'height', 'weight',
        'shoulder_posture', 'stomach_description', 'chest_description',
    ],
    'PantsMeasurement': [
        'pants_waist', 'pants_hip', 'crotch',
        'thigh', 'knee', 'cuff', 'pants_length', 'belly',
        'height', 'weight', 'stomach_description',
    ],
    'ShortsMeasurement': [
        'pants_waist', 'pants_hip', 'crotch',
        'thigh', 'knee', 'cuff', 'pants_length', 'belly',
        'height', 'weight', 'stomach_description',
    ],
    'SkirtMeasurement': [
        'pants_waist', 'hips', 'height', 'weight',
    ],
    'SuitMeasurement': [
        'neck', 'shoulder', 'biceps', 'chest', 'stomach',
        'hips', 'front', 'back',
        'pants_waist', 'pants_hip', 'belly', 'crotch',
        'thigh', 'knee', 'cuff',
        'height', 'weight',
        'shoulder_posture', 'chest_description', 'stomach_description',
    ],
    'DressMeasurement': [
        'neck', 'shoulder', 'sleeve', 'biceps',
        'high_chest', 'chest', 'stomach', 'upper_hips', 'hips',
        'deep_front', 'deep_back',
        'shoulder_to_middle_breast', 'shoulder_to_under_breast',
        'middle_breast_to_middle_breast',
        'shoulder_to_back', 'shoulder_to_waist',
        'height', 'weight',
    ],
    'BlouseMeasurement': [
        'neck', 'shoulder', 'sleeve', 'biceps',
        'high_chest', 'chest', 'stomach', 'upper_hips', 'hips',
        'shoulder_to_middle_breast', 'shoulder_to_under_breast',
        'middle_breast_to_middle_breast',
        'shoulder_to_back', 'shoulder_to_waist',
        'height', 'weight',
    ],
}
_MEAS_FIELD_ORDER = {
    "JacketMeasurement":  ["sleeve", "length"],
    "ShirtMeasurement":   ["neck", "sleeve", "length"],
    "PantsMeasurement":   ["length"],
    "VestMeasurement":    ["length"],
    "CoatMeasurement":    ["sleeve", "length"],
    "SuitMeasurement":    ["sleeve", "jacket_length", "pants_length"],
    "DressMeasurement":   ["neck", "length", "front", "back"],
    "BlouseMeasurement":  ["neck", "length", "front", "back"],
    "SkirtMeasurement":   ["length"],
    "ShortsMeasurement":  ["length"],
    "ShoesMeasurement":   ["foot_length", "foot_width", "foot_instep"],
    "BeltMeasurement":    ["belt_waist"],
}


# Unified display order for all garments
UNIFIED_ORDER = [
    ('neck',                          'Neck'),
    ('shoulder',                      'Shoulder'),
    ('sleeve',                        'Sleeve'),
    ('biceps',                        'Biceps'),
    ('chest',                         'Chest'),
    ('stomach',                       'Stomach'),
    ('hips',                          'Hip'),
    ('length',                        'Length'),
    ('jacket_length',                 'Jacket Length'),
    ('front',                         'Front'),
    ('back',                          'Back'),
    ('pants_waist',                   'Pants Waist'),
    ('pants_hip',                     'Pants Hip'),
    ('belly',                         'Belly'),
    ('crotch',                        'Crotch'),
    ('thigh',                         'Thigh'),
    ('knee',                          'Knee'),
    ('cuff',                          'Cuff'),
    ('pants_length',                  'Pants Length'),
    ('shoulder_posture',              'Shoulder Posture'),
    ('chest_description',             'Chest Type'),
    ('stomach_description',           'Stomach Type'),
    ('height',                        'Height'),
    ('weight',                        'Weight'),
    ('high_chest',                    'High Chest'),
    ('upper_hips',                    'Upper Hips'),
    ('deep_front',                    'Deep Front'),
    ('deep_back',                     'Deep Back'),
    ('shoulder_to_middle_breast',     'Sh. to Middle Breast'),
    ('shoulder_to_under_breast',      'Sh. to Under Breast'),
    ('middle_breast_to_middle_breast','Middle Breast'),
    ('shoulder_to_back',              'Sh. to Back'),
    ('shoulder_to_waist',             'Sh. to Waist'),
    ('foot_length',                   'Foot Length'),
    ('foot_width',                    'Foot Width'),
    ('foot_instep',                   'Foot Instep'),
    ('belt_waist',                    'Belt Waist'),
]

# All body field names (for fallback when no garment mapping found)
ALL_BODY_FIELD_NAMES = set(fname for fname, _ in UNIFIED_ORDER)


def _get_measurement_fields(item):
    """
    Returns a single unified measurement list in tailor-logical order.
    Body fields are filtered to garment-relevant fields only.
    Garment-specific value takes priority over body value for same field name.
    Only shows fields with actual values.
    """
    body_vals = {}
    garment_model_name = None

    # ── Collect garment-relevant body measurement values ──
    try:
        bm = item.body_measurement
        garment_model_name = item.product_type.measurement_model
        # Only collect body fields relevant to this garment
        allowed = set(GARMENT_BODY_FIELDS.get(garment_model_name, ALL_BODY_FIELD_NAMES))
        for f in bm._meta.get_fields():
            if not hasattr(f, 'column'):
                continue
            if f.name in ('id', 'order_item', 'gender'):
                continue
            if f.name not in allowed:
                continue
            val = getattr(bm, f.name, None)
            if val not in (None, '', 0, 0.0):
                get_disp = getattr(bm, f'get_{f.name}_display', None)
                body_vals[f.name] = get_disp() if get_disp else val
    except Exception:
        pass

    # ── Collect garment-specific values ──────────────────
    garment_vals = {}
    try:
        if not garment_model_name:
            garment_model_name = item.product_type.measurement_model
        base  = item.measurement
        model = apps.get_model("orders", garment_model_name)
        m     = model.objects.filter(base=base).first()
        if m:
            # Use explicit field list from _MEAS_FIELD_ORDER for reliability
            field_names = _MEAS_FIELD_ORDER.get(model.__name__, [])
            for fname in field_names:
                try:
                    val = getattr(m, fname, None)
                    if val not in (None, '', 0, 0.0):
                        garment_vals[fname] = val
                except Exception:
                    continue

            # ── Garment-specific field remapping ──────────────
            # PantsMeasurement.length → pants_length
            # (avoids showing both "Length" and "Pants Length")
            if garment_model_name == 'PantsMeasurement':
                if 'length' in garment_vals:
                    garment_vals['pants_length'] = garment_vals.pop('length')

            # SuitMeasurement.jacket_length → length
            if garment_model_name == 'SuitMeasurement':
                if 'jacket_length' in garment_vals:
                    garment_vals['length'] = garment_vals.pop('jacket_length')

    except Exception:
        pass

    # ── Build display list ────────────────────────────────
    result = []
    for fname, label in UNIFIED_ORDER:
        val = garment_vals.get(fname, body_vals.get(fname))
        if val not in (None, '', 0, 0.0, False):
            result.append((label, val))
    return result



# ─────────────────────────────────────────────────────────
# Quick status change
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_quick_status(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    if request.method != "POST":
        return HttpResponse(status=405)

    new_status    = request.POST.get("status", "")
    valid_choices = [s[0] for s in Order.STATUS_CHOICES if s[0] != "canceled"]
    if new_status in valid_choices and order.status != "canceled":
        order.status = new_status
        order.save()
        cache.delete(f"order_status_counts_{tenant.id}")

    response = render(request, "orders/partials/_status_select.html",
                      {"order": order, "status_choices": Order.STATUS_CHOICES})
    response["HX-Trigger"] = json.dumps({
        "statusChanged": {"orderId": order.pk, "status": order.status}
    })
    return response


# ─────────────────────────────────────────────────────────
# Add payment
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_add_payment(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    if request.method != "POST":
        return HttpResponse(status=405)

    form = PaymentForm(request.POST, request.FILES, prefix="qp")
    form.fields["original_amount"].required = True

    if form.is_valid():
        cd    = form.cleaned_data
        ptype = cd.get("type") or "deposit"
        amount = cd.get("original_amount")
        if ptype == "refund" or (amount is not None and amount < 0):
            approved = False
            try:
                record   = order.cancellation
                approved = bool(record.approved_by_id)
            except Exception:
                pass
            if not approved:
                return render(request, "orders/partials/_payment_history.html",
                              {"order": order,
                               "payments": order.payments.select_related("recorded_by").all(),
                               "quick_pay_form": PaymentForm(prefix="qp"),
                               "pay_form_error": "Refund not allowed — owner must approve the cancellation first."})

        Payment.objects.create(
            order                = order,
            recorded_by          = request.user,
            original_amount      = cd["original_amount"],
            currency             = cd.get("currency")             or "THB",
            exchange_rate_to_thb = cd.get("exchange_rate_to_thb") or 1,
            method               = cd.get("method")               or "cash",
            type                 = ptype,
            notes                = cd.get("notes")                or "",
            proof_image          = cd.get("proof_image")          or None,
        )

        # Auto-lock total on first payment
        if not order.total_locked and ptype not in ("refund",):
            from django.utils import timezone
            order.total_locked    = True
            order.total_locked_at = timezone.now()
            order.total_locked_by = request.user
            order.save(update_fields=["total_locked", "total_locked_at", "total_locked_by"])

        payments = order.payments.select_related("recorded_by").all()
        response = render(request, "orders/partials/_payment_history.html",
                          {"order": order, "payments": payments,
                           "quick_pay_form": PaymentForm(prefix="qp")})
        response["HX-Trigger"] = json.dumps({"paymentAdded": True})
        return response

    return render(request, "orders/partials/_payment_history.html",
                  {"order": order,
                   "payments": order.payments.select_related("recorded_by").all(),
                   "quick_pay_form": form,
                   "pay_form_open": True})


# ─────────────────────────────────────────────────────────
# Cancellation flow
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_cancel(request, pk):
    from django.utils import timezone
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    order = get_object_or_404(Order, pk=pk, tenant=tenant)

    if order.status == "canceled":
        try:
            record = order.cancellation
        except Exception:
            record = None
        return render(request, "orders/partials/_cancel_form.html", {
            "order":            order,
            "record":           record,
            "already_canceled": True,
        })

    if request.method == "GET":
        return render(request, "orders/partials/_cancel_form.html", {
            "order": order,
            "form":  CancellationForm(),
        })

    existing = CancellationRecord.objects.filter(order=order).first()
    if existing:
        if order.status != "canceled":
            order.status = "canceled"
            order.save()
            cache.delete(f"order_status_counts_{tenant.id}")
        response = HttpResponse("")
        response["HX-Trigger"] = json.dumps({
            "orderCanceled": {"pk": order.pk, "orderNumber": order.order_number},
        })
        return response

    form = CancellationForm(request.POST)
    if not form.is_valid():
        response = render(request, "orders/partials/_cancel_form.html", {
            "order": order,
            "form":  form,
        })
        response["HX-Retarget"] = "#cancel-modal-body"
        response["HX-Reswap"]   = "innerHTML"
        return response

    cancellation             = form.save(commit=False)
    cancellation.order       = order
    cancellation.canceled_by = request.user
    cancellation.save()

    order.status = "canceled"
    order.save()
    cache.delete(f"order_status_counts_{tenant.id}")

    response = HttpResponse("")
    response["HX-Trigger"] = json.dumps({
        "orderCanceled": {"pk": order.pk, "orderNumber": order.order_number},
    })
    return response


# ─────────────────────────────────────────────────────────
# Approve / reject partial refund
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_approve_refund(request, pk):
    from django.utils import timezone
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    order        = get_object_or_404(Order, pk=pk, tenant=tenant)
    cancellation = get_object_or_404(CancellationRecord, order=order)

    if request.method != "POST":
        return HttpResponse(status=405)

    action = request.POST.get("action", "")
    if action == "approve" and not cancellation.approved_by:
        cancellation.approved_by = request.user
        cancellation.resolved_at = timezone.now()
        cancellation.save()
    elif action == "reject":
        cancellation.resolution       = "none"
        cancellation.resolution_notes = (
            (cancellation.resolution_notes or "") +
            f"\n[Rejected by {request.user.username}]"
        ).strip()
        cancellation.save()

    pending_refunds = CancellationRecord.objects.filter(
        resolution="partial_refund",
        approved_by=None,
        order__tenant=tenant,
    ).select_related("order__client", "canceled_by")
    response = render(request, "admin_dashboard/partials/_pending_approvals.html",
                      {"pending_refunds": pending_refunds})
    response["HX-Trigger"] = json.dumps({"refreshDashboard": True})
    return response


# ─────────────────────────────────────────────────────────
# Pending approvals
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def pending_approvals(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("")
    pending_refunds = CancellationRecord.objects.filter(
        resolution="partial_refund",
        approved_by=None,
        order__tenant=tenant,
    ).select_related("order__client", "canceled_by").order_by("-order__created_at")
    return render(request, "admin_dashboard/partials/_pending_approvals.html",
                  {"pending_refunds": pending_refunds})


# ─────────────────────────────────────────────────────────
# Client profile modal
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def client_profile(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    client = get_object_or_404(Client, pk=pk)
    all_orders = list(
        client.orders.filter(tenant=tenant)
        .select_related("delivery")
        .order_by("-created_at")
    )
    return render(request, "orders/partials/_client_profile_modal.html", {
        "client":            client,
        "form":              ClientEditForm(instance=client),
        "recent_orders":     all_orders[:5],
        "remaining_orders":  all_orders[5:],
        "total_order_count": len(all_orders),
        "total_spent":       client.total_spent(),
        "editing":           False,
    })


@user_passes_test(staff_check)
def client_edit(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    client = get_object_or_404(Client, pk=pk)
    if request.method != "POST":
        return HttpResponse(status=405)

    form = ClientEditForm(request.POST, instance=client)
    if form.is_valid():
        form.save()
        response = HttpResponse("")
        response["HX-Trigger"] = json.dumps({"clientSaved": {"pk": client.pk}})
        return response

    all_orders = list(client.orders.filter(tenant=tenant).select_related("delivery").order_by("-created_at"))
    response = render(request, "orders/partials/_client_profile_modal.html", {
        "client":            client,
        "form":              form,
        "recent_orders":     all_orders[:5],
        "remaining_orders":  all_orders[5:],
        "total_order_count": len(all_orders),
        "total_spent":       client.total_spent(),
        "editing":           True,
    })
    response["HX-Retarget"] = "#client-profile-modal-body"
    response["HX-Reswap"]   = "innerHTML"
    return response


# ─────────────────────────────────────────────────────────
# Delivery proof upload
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_delivery_proof(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    order = get_object_or_404(Order, pk=pk, tenant=tenant)

    try:
        delivery = order.delivery
    except Exception:
        return HttpResponse("No delivery record for this order.", status=400)

    if request.method == "GET":
        return render(request, "orders/partials/_delivery_proof_form.html", {
            "order":    order,
            "delivery": delivery,
        })

    if request.method == "POST":
        image = request.FILES.get("proof_image")
        if image:
            delivery.proof_image = image
            delivery.save()
        response = render(request, "orders/partials/_delivery_proof_form.html", {
            "order":    order,
            "delivery": delivery,
            "saved":    True,
        })
        response["HX-Trigger"] = json.dumps({"deliveryProofSaved": {"pk": order.pk}})
        return response

    return HttpResponse(status=405)


# ─────────────────────────────────────────────────────────
# CSV Export — column-aware
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def export_csv(request):
    import csv

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    def _bal(o):
        try:    return o.balance_due
        except: return ""

    ALL_COLS = [
        ("order_number",    "Order #",              lambda o, x: o.order_number),
        ("created",         "Created",               lambda o, x: o.created_at.strftime("%d/%m/%Y") if o.created_at else ""),
        ("status",          "Status",                lambda o, x: o.get_status_display()),
        ("urgent",          "Urgent",                lambda o, x: "Yes" if o.is_urgent else ""),
        ("client_name",     "Client",                lambda o, x: o.client.name),
        ("phone",           "Phone",                 lambda o, x: o.client.phone or ""),
        ("email",           "Email",                 lambda o, x: o.client.email or ""),
        ("hotel",           "Hotel",                 lambda o, x: o.hotel_name or ""),
        ("room",            "Room",                  lambda o, x: o.room_number or ""),
        ("fitting_date",    "Fitting Date",          lambda o, x: o.fitting_date.strftime("%d/%m/%Y") if o.fitting_date else ""),
        ("ready_date",      "Ready Date",            lambda o, x: o.ready_date.strftime("%d/%m/%Y") if o.ready_date else ""),
        ("departure_date",  "Departure Date",        lambda o, x: o.departure_date.strftime("%d/%m/%Y") if o.departure_date else ""),
        ("delivery_date",   "Delivery Date",         lambda o, x: o.delivery_date.strftime("%d/%m/%Y") if o.delivery_date else ""),
        ("total_amount",    "Total Amount",          lambda o, x: o.total_amount or ""),
        ("currency",        "Currency",              lambda o, x: o.total_currency or ""),
        ("balance_due",     "Balance Due (THB)",     lambda o, x: _bal(o)),
        ("hotel_delivery",  "Hotel (Delivery)",      lambda o, x: x.get("d_hotel", "")),
        ("room_delivery",   "Room (Delivery)",       lambda o, x: x.get("d_room", "")),
        ("items",           "Items",                 lambda o, x: x.get("items", "")),
        ("staff",           "Staff",                 lambda o, x: x.get("staff", "")),
        ("payments",        "Payments",              lambda o, x: x.get("payments", "")),
        ("total_collected", "Total Collected (THB)", lambda o, x: x.get("collected", "")),
    ]

    # Which columns to include — default is all
    requested = request.GET.getlist("cols")
    if requested:
        selected = [c for c in ALL_COLS if c[0] in requested]
        if not any(c[0] == "order_number" for c in selected):
            selected.insert(0, ALL_COLS[0])
    else:
        selected = ALL_COLS

    # Filters — mirror orders_table
    status    = request.GET.get("status")    or ""
    q         = (request.GET.get("q") or "").strip()
    from_date = request.GET.get("from_date") or ""
    to_date   = request.GET.get("to_date")   or ""
    staff_id  = request.GET.get("staff_id")  or ""
    urgent    = request.GET.get("urgent")    or ""

    orders = (
        Order.objects.filter(tenant=tenant)
        .select_related("client", "delivery")
        .prefetch_related("items__product_type", "staff_assignments__user", "payments")
        .order_by("-created_at")
    )
    min_amount = request.GET.get("min_amount") or ""
    max_amount = request.GET.get("max_amount") or ""

    if status:    orders = orders.filter(status=status)
    if q:         orders = orders.filter(Q(order_number__icontains=q) | Q(client__name__icontains=q) | Q(client__phone__icontains=q))
    if from_date: orders = orders.filter(created_at__date__gte=from_date)
    if to_date:   orders = orders.filter(created_at__date__lte=to_date)
    if staff_id:  orders = orders.filter(staff_assignments__user_id=staff_id).distinct()
    if urgent:    orders = orders.filter(is_urgent=True)
    if min_amount:
        try:    orders = orders.filter(total_amount__gte=float(min_amount))
        except: pass
    if max_amount:
        try:    orders = orders.filter(total_amount__lte=float(max_amount))
        except: pass

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'
    response.write("\ufeff")  # UTF-8 BOM for Excel
    writer = csv.writer(response)
    writer.writerow([c[1] for c in selected])

    for order in orders:
        ctx = {
            "items":     "; ".join(
                f"{i.product_type.name if i.product_type else '?'} \u00d7{i.quantity}"
                for i in order.items.all()
            ),
            "staff":     "; ".join(
                f"{s.user.get_full_name() or s.user.username} ({s.get_role_display()})"
                for s in order.staff_assignments.all()
            ),
            "payments":  "; ".join(
                f"{p.get_type_display()} {p.original_amount} {p.currency} ({p.get_method_display()})"
                for p in order.payments.all()
            ),
            "collected": sum((p.thb_equivalent or 0) for p in order.payments.all()),
            "d_hotel":   "",
            "d_room":    "",
        }
        if hasattr(order, "delivery") and order.delivery:
            ctx["d_hotel"] = order.delivery.hotel_name or ""
            ctx["d_room"]  = order.delivery.room_number or ""

        writer.writerow([c[2](order, ctx) for c in selected])

    return response


def _build_contact(order, message):
    from urllib.parse import quote as _quote
    phone = (order.client.phone or "").replace("+", "").replace(" ", "")
    raw   = order.client.phone or ""
    msg   = _quote(message)
    return {
        "wa_url":   f"https://wa.me/{phone}?text={msg}",
        "line_url": f"https://line.me/R/ti/p/+{phone}",
        "sms_url":  f"sms:{raw}?body={msg}",
    }


def _get_reminders(tenant, today, days):
    future = today + _timedelta(days=days)
    active = ["new", "pending", "processing", "ready", "alterations"]

    departing_urgent = list(
        Order.objects.filter(
            tenant=tenant,
            hotel_name__isnull=False,
            departure_date__gte=today,
            departure_date__lte=today + _timedelta(days=1),
            status__in=active,
        ).select_related("client"
        ).prefetch_related("staff_assignments__user"
        ).order_by("departure_date")
    )
    for o in departing_urgent:
        msg = (
            f"Hello {o.client.name}! Your order #{o.order_number} is ready. "
            f"We will deliver to {o.hotel_name or ''}"
            f"{', Room ' + o.room_number if o.room_number else ''} "
            f"before your departure on "
            f"{o.departure_date.strftime('%d %b') if o.departure_date else ''}. "
            f"Please confirm delivery time. Thank you! \U0001f64f"
        )
        o.contact_urls = _build_contact(o, msg)

    fitting_today = list(
        Order.objects.filter(
            tenant=tenant,
            fitting_date=today,
            status__in=active,
        ).select_related("client"
        ).prefetch_related("staff_assignments__user"
        ).order_by("order_number")
    )
    for o in fitting_today:
        msg = (
            f"Hello {o.client.name}! Just a reminder that your fitting "
            f"for order #{o.order_number} is scheduled today. "
            f"Please visit us at your convenience. Thank you! \U0001f64f"
        )
        o.contact_urls = _build_contact(o, msg)

    ready_overdue = list(
        Order.objects.filter(
            tenant=tenant,
            status="ready",
        ).filter(
            Q(delivery_date__lt=today) | Q(departure_date__lt=today)
        ).select_related("client"
        ).prefetch_related("staff_assignments__user"
        ).order_by("ready_date")
    )
    for o in ready_overdue:
        msg = (
            f"Hello {o.client.name}! Your order #{o.order_number} has been "
            f"ready and is waiting for you. "
            f"Please let us know when you would like to collect it. Thank you! \U0001f64f"
        )
        o.contact_urls = _build_contact(o, msg)

    departing_soon = list(
        Order.objects.filter(
            tenant=tenant,
            hotel_name__isnull=False,
            departure_date__gt=today + _timedelta(days=1),
            departure_date__lte=future,
            status__in=active,
        ).select_related("client"
        ).prefetch_related("staff_assignments__user"
        ).order_by("departure_date")
    )
    for o in departing_soon:
        msg = (
            f"Hello {o.client.name}! Your order #{o.order_number} will be "
            f"ready before your departure on "
            f"{o.departure_date.strftime('%d %b') if o.departure_date else ''}. "
            f"We will deliver to {o.hotel_name or ''}"
            f"{', Room ' + o.room_number if o.room_number else ''}. "
            f"Thank you for choosing us! \U0001f64f"
        )
        o.contact_urls = _build_contact(o, msg)

    total = (len(departing_urgent) + len(fitting_today) +
             len(ready_overdue) + len(departing_soon))
    return {
        "departing_urgent": departing_urgent,
        "fitting_today":    fitting_today,
        "ready_overdue":    ready_overdue,
        "departing_soon":   departing_soon,
        "total_count":      total,
    }


@user_passes_test(staff_check)
def notifications_count(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("")
    today = _date.today()
    days  = int(request.session.get("reminder_days", 3))
    data  = _get_reminders(tenant, today, days)
    reminder_count = data["total_count"]

    # Add catalogue inquiry count
    inquiry_count = _get_inquiry_count()
    total = reminder_count + inquiry_count

    if total:
        return HttpResponse(str(total))
    return HttpResponse("")


REMINDER_DAYS_OPTIONS = [1, 3, 7, 14]


def _get_inquiry_count():
    """Fetch new inquiry count from fashion_01 API."""
    try:
        import httpx
        r = httpx.get(
            "https://emporiumarmani.com/api/v1/inquiries/count/",
            timeout=3,
        )
        if r.status_code == 200:
            return r.json().get("new_count", 0)
    except Exception:
        pass
    return 0


def _get_inquiries():
    """Fetch active inquiries from fashion_01 API (new, contacted, confirmed, no_reply)."""
    try:
        import httpx
        r = httpx.get(
            "https://emporiumarmani.com/api/v1/inquiries/?status=new,contacted,confirmed,no_reply",
            timeout=3,
        )
        if r.status_code == 200:
            return r.json().get("results", [])
    except Exception:
        pass
    return []


@user_passes_test(staff_check)
def notifications_list(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    today = _date.today()
    days  = int(request.GET.get("days", request.session.get("reminder_days", 3)))
    if days not in REMINDER_DAYS_OPTIONS:
        days = 3
    request.session["reminder_days"] = days
    try:
        data = _get_reminders(tenant, today, days)
    except Exception as e:
        print(f"ERROR notifications_list: {type(e).__name__}: {e}")
        return HttpResponse(
            f'<div class="px-3 py-4 text-center text-muted small">'
            f'<i class="bi bi-exclamation-circle text-warning d-block mb-2" style="font-size:1.5rem"></i>'
            f'Could not load reminders.<br>'
            f'<span style="font-size:0.7rem">{type(e).__name__}: {e}</span>'
            f'</div>'
        )

    # Fetch inquiries from catalogue API
    inquiries = _get_inquiries()

    return render(request, "orders/partials/_notifications_dropdown.html", {
        **data,
        "days":          days,
        "days_options":  REMINDER_DAYS_OPTIONS,
        "today":         today,
        "inquiries":     inquiries,
        "inquiry_count": len(inquiries),
    })


@user_passes_test(staff_check)
def inquiry_update(request, inquiry_id):
    """Update inquiry status via HTMX — called from notification bell."""
    if request.method not in ('POST', 'PATCH'):
        return HttpResponse(status=405)

    # Django doesn't parse PATCH body into request.POST — read manually
    status = request.POST.get('status')
    if not status:
        try:
            import json
            data   = json.loads(request.body)
            status = data.get('status')
        except Exception:
            from urllib.parse import parse_qs
            data   = parse_qs(request.body.decode())
            status = data.get('status', [None])[0]
    valid  = ['new', 'contacted', 'confirmed', 'no_reply', 'converted', 'closed']
    if status not in valid:
        return HttpResponse('Invalid status', status=400)

    try:
        import httpx
        r = httpx.patch(
            f"https://emporiumarmani.com/api/v1/inquiries/{inquiry_id}/",
            json={'status': status},
            timeout=5,
        )
        if r.status_code in (200, 204):
            # Return updated card or empty div if closed
            if status == 'closed':
                return HttpResponse(
                    f'<div id="inq-{inquiry_id}" class="px-3 py-2 border-bottom text-muted small">'
                    f'<i class="bi bi-check-circle text-success me-1"></i>Inquiry closed.</div>'
                )
            inq = r.json()
            # Re-render the inquiry card with updated status badge
            status_colors = {
                'contacted': 'warning',
                'confirmed': 'success',
                'no_reply':  'secondary',
            }
            color = status_colors.get(status, 'secondary')
            return HttpResponse(
                f'<div id="inq-{inquiry_id}" class="px-3 py-2 border-bottom">'
                f'<div class="small fw-semibold">{inq["name"]} '
                f'<span class="badge text-bg-{color}">{status.replace("_"," ").title()}</span></div>'
                f'<div class="small text-muted">{inq["phone"]}</div>'
                f'<div class="small text-muted mt-1" style="font-size:0.7rem">{inq["message"][:100]}</div>'
                f'</div>'
            )
    except Exception as e:
        return HttpResponse(f'Error: {e}', status=500)

    return HttpResponse(status=200)
@user_passes_test(staff_check)
def production_bill_view(request, order_pk, item_pk):
    from django.utils import timezone
    from django.db import transaction

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    order = get_object_or_404(Order, pk=order_pk, tenant=tenant)
    item  = get_object_or_404(OrderItem, pk=item_pk, order=order)

    try:
        bill = item.production_bill
    except Exception:
        bill = None

    variation_types = []
    fabric_zones    = []
    monogram_styles = []

    if item.product_type:
        target = TargetItem.objects.filter(
            name__iexact=item.product_type.name
        ).first()
        if target:
            variation_types = list(
                VariationType.objects.filter(target_items=target)
                .prefetch_related("options")
                .order_by("order", "name")
            )
        fabric_zones = list(
            FabricZone.objects.filter(product_type=item.product_type)
            .order_by("order", "name")
        )
        monogram_styles = list(
            VariationOption.objects.filter(
                type__name__icontains="monogram"
            ).order_by("type__order", "order", "name")
        )

    quantity = item.quantity or 1
    pieces   = list(range(1, quantity + 1))

    existing_styles = {}
    existing_sets   = {}
    if bill:
        existing_styles = {
            str(s.variation_type_id): str(s.chosen_option_id)
            for s in bill.style_selections.all()
        }
        for fset in bill.fabric_sets.select_related().prefetch_related(
            "zone_entries__zone", "monogram__style"
        ):
            existing_sets[fset.piece_number] = fset

    if request.method == "GET":
        measurement_fields = _get_measurement_fields(item)
        client_photos  = list(order.client_photos.exclude(image='').order_by('person_number', 'photo_type'))
        item_photos    = list(item.photos.exclude(image='').order_by('pk'))
        scratch_notes  = list(order.scratch_notes.exclude(image='').order_by('created_at'))
        return render(request, "orders/production_bill.html", {
            "order":              order,
            "item":               item,
            "bill":               bill,
            "variation_types":    variation_types,
            "fabric_zones":       fabric_zones,
            "monogram_styles":    monogram_styles,
            "pieces":             pieces,
            "existing_styles":    existing_styles,
            "existing_sets":      existing_sets,
            "measurement_fields": measurement_fields,
            "client_photos":      client_photos,
            "item_photos":        item_photos,
            "scratch_notes":      scratch_notes,
        })

    confirm = "confirm" in request.POST

    with transaction.atomic():
        if not bill:
            bill = ProductionBill.objects.create(
                order_item=item,
                created_by=request.user,
            )

        bill.gender = request.POST.get("gender", "men")
        bill.notes  = request.POST.get("notes", "")
        if confirm:
            bill.status       = "confirmed"
            bill.confirmed_by = request.user
            bill.confirmed_at = timezone.now()
        bill.save()

        bill.style_selections.all().delete()
        for vtype in variation_types:
            option_id = request.POST.get(f"style_{vtype.pk}")
            if option_id:
                try:
                    BillStyleSelection.objects.create(
                        bill=bill,
                        variation_type=vtype,
                        chosen_option_id=int(option_id),
                    )
                except Exception:
                    pass

        bill.fabric_sets.all().delete()
        for n in pieces:
            fset = FabricSet.objects.create(
                bill=bill,
                piece_number=n,
                label=request.POST.get(f"piece_{n}_label", ""),
            )
            for z_order, zone in enumerate(fabric_zones):
                code  = request.POST.get(f"piece_{n}_zone_{zone.pk}_code",  "")
                color = request.POST.get(f"piece_{n}_zone_{zone.pk}_color", "")
                notes = request.POST.get(f"piece_{n}_zone_{zone.pk}_notes", "")
                FabricZoneEntry.objects.create(
                    fabric_set=fset,
                    zone=zone,
                    fabric_code=code,
                    color=color,
                    notes=notes,
                    order=z_order,
                )
            extra_labels = request.POST.getlist(f"piece_{n}_extra_label")
            extra_codes  = request.POST.getlist(f"piece_{n}_extra_code")
            extra_colors = request.POST.getlist(f"piece_{n}_extra_color")
            for idx, elabel in enumerate(extra_labels):
                if elabel.strip():
                    FabricZoneEntry.objects.create(
                        fabric_set=fset,
                        zone_label=elabel,
                        fabric_code=extra_codes[idx] if idx < len(extra_codes) else "",
                        color=extra_colors[idx]  if idx < len(extra_colors) else "",
                        order=len(fabric_zones) + idx,
                    )
            if request.POST.get(f"piece_{n}_has_monogram"):
                style_id = request.POST.get(f"piece_{n}_mono_style") or None
                Monogram.objects.create(
                    fabric_set=fset,
                    text=request.POST.get(f"piece_{n}_mono_text", ""),
                    style_id=style_id,
                    color=request.POST.get(f"piece_{n}_mono_color", ""),
                    position=request.POST.get(f"piece_{n}_mono_position", ""),
                )

    if confirm:
        return redirect("orders:production_bill_print", pk=bill.pk)

    messages.success(request, "Bill saved as draft.")
    return redirect("orders:production_bill", order_pk=order.pk, item_pk=item.pk)


@user_passes_test(staff_check)
def production_bill_print(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    bill = get_object_or_404(
        ProductionBill.objects
        .select_related(
            "order_item__order__client",
            "order_item__order__signature",
            "order_item__product_type",
            "order_item__measurement",
            "confirmed_by",
            "created_by",
        )
        .prefetch_related(
            "style_selections__variation_type",
            "style_selections__chosen_option",
            "fabric_sets__zone_entries__zone",
            "fabric_sets__monogram__style",
        ),
        pk=pk,
        order_item__order__tenant=tenant,
    )

    # Auto-confirm on first print
    if not bill.confirmed_at:
        from django.utils import timezone
        bill.status       = "confirmed"
        bill.confirmed_at = timezone.now()
        bill.confirmed_by = request.user
        bill.save(update_fields=["status", "confirmed_at", "confirmed_by"])

    measurement_fields = _get_measurement_fields(bill.order_item)
    client_photos  = list(bill.order_item.order.client_photos.exclude(image='').order_by('person_number', 'photo_type'))
    item_photos    = list(bill.order_item.photos.exclude(image='').order_by('pk'))
    scratch_notes  = list(bill.order_item.order.scratch_notes.exclude(image='').order_by('created_at'))

    # sig=1 → client bill with signature, sig=0 → factory bill without
    show_signature = request.GET.get("sig", "1") == "1"

    return render(request, "orders/production_bill_print.html", {
        "bill":               bill,
        "order":              bill.order_item.order,
        "item":               bill.order_item,
        "measurement_fields": measurement_fields,
        "fabric_sets":        bill.fabric_sets.all().order_by("piece_number"),
        "style_selections":   bill.style_selections.all().order_by("variation_type__order"),
        "client_photos":      client_photos,
        "item_photos":        item_photos,
        "scratch_notes":      scratch_notes,
        "show_signature":     show_signature,
    })


@user_passes_test(staff_check)
def production_bill_pdf(request, pk):
    """Generate PDF of production bill for sharing via WhatsApp/LINE."""
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    bill = get_object_or_404(
        ProductionBill.objects
        .select_related(
            "order_item__order__client",
            "order_item__order__signature",
            "order_item__product_type",
            "order_item__measurement",
            "confirmed_by",
            "created_by",
        )
        .prefetch_related(
            "style_selections__variation_type",
            "style_selections__chosen_option",
            "fabric_sets__zone_entries__zone",
            "fabric_sets__monogram__style",
        ),
        pk=pk,
        order_item__order__tenant=tenant,
    )

    measurement_fields = _get_measurement_fields(bill.order_item)
    client_photos  = list(bill.order_item.order.client_photos.exclude(image='').order_by('person_number', 'photo_type'))
    item_photos    = list(bill.order_item.photos.exclude(image='').order_by('pk'))
    scratch_notes  = list(bill.order_item.order.scratch_notes.exclude(image='').order_by('created_at'))
    show_signature = request.GET.get("sig", "0") == "1"

    ctx = {
        "bill":               bill,
        "order":              bill.order_item.order,
        "item":               bill.order_item,
        "measurement_fields": measurement_fields,
        "fabric_sets":        bill.fabric_sets.all().order_by("piece_number"),
        "style_selections":   bill.style_selections.all().order_by("variation_type__order"),
        "client_photos":      client_photos,
        "item_photos":        item_photos,
        "scratch_notes":      scratch_notes,
        "show_signature":     show_signature,
        "pdf_mode":           True,
    }

    html_string = render_to_string("orders/production_bill_print.html", ctx, request=request)

    try:
        from weasyprint import HTML, CSS
        pdf_bytes = HTML(
            string=html_string,
            base_url=request.build_absolute_uri('/')
        ).write_pdf()

        order_num = bill.order_item.order.order_number
        item_name = bill.order_item.product_type.name if bill.order_item.product_type else 'item'
        copy_type = 'shop' if show_signature else 'factory'
        filename  = f"bill_{order_num}_{item_name}_{copy_type}.pdf".replace(' ', '_')

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        return HttpResponse(f"PDF generation failed: {e}", status=500)


@user_passes_test(staff_check)
def bill_toggle_sent(request, pk):
    from django.utils import timezone
    tenant = getattr(request, "tenant", None)
    bill   = get_object_or_404(
        ProductionBill, pk=pk,
        order_item__order__tenant=tenant
    )
    if request.method == "POST":
        if bill.sent_to_factory:
            bill.sent_to_factory    = False
            bill.sent_to_factory_at = None
            bill.sent_to_factory_by = None
        else:
            bill.sent_to_factory    = True
            bill.sent_to_factory_at = timezone.now()
            bill.sent_to_factory_by = request.user
        bill.save(update_fields=[
            "sent_to_factory", "sent_to_factory_at", "sent_to_factory_by"
        ])
    sent = bill.sent_to_factory
    ts   = bill.sent_to_factory_at
    who  = bill.sent_to_factory_by
    if sent:
        html = (
            f'<div id="factory-badge" class="d-flex align-items-center gap-2">'
            f'<span class="badge text-bg-success">'
            f'<i class="bi bi-check-circle me-1"></i>Sent to factory</span>'
            f'<span class="text-muted" style="font-size:0.72rem">'
            f'{ts.strftime("%d %b %Y %H:%M") if ts else ""}'
            f'{"  · " + who.get_full_name() if who and who.get_full_name() else ""}'
            f'</span>'
            f'<button class="btn btn-sm btn-outline-secondary py-0 px-2" style="font-size:0.72rem"'
            f' hx-post="/bill/{bill.pk}/sent/" hx-target="#factory-badge" hx-swap="outerHTML"'
            f' hx-confirm="Undo sent-to-factory mark?">Undo</button>'
            f'</div>'
        )
    else:
        html = (
            f'<div id="factory-badge">'
            f'<button class="btn btn-sm btn-success py-0 px-2" style="font-size:0.72rem"'
            f' hx-post="/bill/{bill.pk}/sent/" hx-target="#factory-badge" hx-swap="outerHTML">'
            f'<i class="bi bi-send me-1"></i>Mark as sent to factory</button>'
            f'</div>'
        )
    return HttpResponse(html)


# ─────────────────────────────────────────────────────────
# Total amount lock / unlock
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_toggle_lock(request, pk):
    from django.utils import timezone
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    if request.method != "POST":
        return HttpResponse(status=405)

    order = get_object_or_404(Order, pk=pk, tenant=tenant)

    # Only owner/manager can lock or unlock
    try:
        user_role = request.user.staff_profile.role
    except Exception:
        user_role = "owner" if request.user.is_superuser else "staff"

    if user_role not in ("owner", "manager") and not request.user.is_superuser:
        return HttpResponse(
            '<div class="alert alert-danger py-2 small mb-0">'
            'Only owner or manager can lock / unlock the total amount.'
            '</div>',
            status=403
        )

    if order.total_locked:
        # Unlock
        order.total_locked    = False
        order.total_locked_at = None
        order.total_locked_by = None
    else:
        # Lock
        order.total_locked    = True
        order.total_locked_at = timezone.now()
        order.total_locked_by = request.user

    order.save(update_fields=["total_locked", "total_locked_at", "total_locked_by"])

    # Redirect to refresh — include ?step= so wizard stays on correct step
    from_step = request.POST.get("from_step", "")
    if from_step:
        # Coming from edit form — redirect back to same step
        redirect_url = f"/{order.pk}/edit/?step={from_step}"
    else:
        # Coming from order detail modal — just refresh page
        redirect_url = None

    response = HttpResponse("")
    if redirect_url:
        response["HX-Redirect"] = redirect_url
    else:
        response["HX-Refresh"] = "true"
    return response


# ─────────────────────────────────────────────────────────
# Reorder — create a new order linked to a previous one
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_reorder(request, pk):
    """
    Create a new order pre-filled with the same client + items
    from an existing order. Sets parent_order FK to link them.
    Measurements are NOT copied — staff takes fresh measurements.
    Redirects to the new order's edit form.
    """
    from django.db import transaction
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    if request.method != "POST":
        return HttpResponse(status=405)

    original = get_object_or_404(Order, pk=pk, tenant=tenant)

    with transaction.atomic():
        # Create new order linked to original
        new_order = Order.objects.create(
            tenant        = tenant,
            client        = original.client,
            parent_order  = original,
            status        = "new",
            total_amount  = original.total_amount,
            total_currency = original.total_currency,
            # Copy address snapshot
            street_address = original.street_address,
            city           = original.city,
            state          = original.state,
            postcode       = original.postcode,
            country        = original.country,
            note           = original.note or "",
        )
        cache.delete(f"order_status_counts_{tenant.id}")

        # Copy items (product type + name + quantity + price)
        # Measurements NOT copied — tailor takes fresh ones
        for item in original.items.select_related("product_type").all():
            OrderItem.objects.create(
                order        = new_order,
                product_type = item.product_type,
                product_name = item.product_name,
                quantity     = item.quantity,
                price        = item.price,
            )

    messages.success(
        request,
        f"Reorder created as #{new_order.order_number} "
        f"— linked to original #{original.order_number}."
    )
    # Use HX-Redirect so HTMX does a full page navigation instead of a content swap
    from django.urls import reverse
    response = HttpResponse("")
    response["HX-Redirect"] = reverse("orders:order_edit", kwargs={"pk": new_order.pk})
    return response


# ─────────────────────────────────────────────────────────
# Temp photo upload — called immediately when file selected
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def upload_temp_photo(request):
    """Immediately store an uploaded file; returns {uuid, url}."""
    from django.http import JsonResponse
    if request.method != "POST" or "file" not in request.FILES:
        return JsonResponse({"error": "No file"}, status=400)
    temp = TempPhoto(image=request.FILES["file"])
    temp.save()
    return JsonResponse({"uuid": str(temp.uuid), "url": temp.image.url})


# ─────────────────────────────────────────────────────────
# Documents — Receipt, Invoice, Shipping Label
# ─────────────────────────────────────────────────────────
def _order_doc_context(pk, tenant):
    """Shared queryset for all three document views."""
    from django.shortcuts import get_object_or_404
    order = get_object_or_404(
        Order.objects
        .select_related(
            "client", "tenant",
            "signature",
        )
        .prefetch_related(
            "items__product_type",
            "payments__recorded_by",
            "delivery",
        ),
        pk=pk, tenant=tenant,
    )
    items    = list(order.items.select_related("product_type").all())
    payments = list(order.payments.exclude(type="refund").order_by("created_at"))
    refunds  = list(order.payments.filter(type="refund").order_by("created_at"))
    collected = sum(p.thb_equivalent or 0 for p in payments)
    refunded  = sum(abs(p.thb_equivalent or 0) for p in refunds)
    has_individual = any(item.price for item in items)
    delivery = getattr(order, "delivery", None)
    try:
        signature = order.signature
    except Exception:
        signature = None
    return {
        "order":           order,
        "tenant":          tenant,
        "items":           items,
        "payments":        payments,
        "refunds":         refunds,
        "collected_thb":   collected,
        "refunded_thb":    refunded,
        "has_individual":  has_individual,
        "delivery":        delivery,
        "signature":       signature,
    }


@user_passes_test(staff_check)
def order_receipt_view(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    ctx = _order_doc_context(pk, tenant)
    return render(request, "orders/docs/receipt.html", ctx)


@user_passes_test(staff_check)
def order_invoice_view(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    ctx = _order_doc_context(pk, tenant)
    return render(request, "orders/docs/invoice.html", ctx)


@user_passes_test(staff_check)
def order_shipping_label_view(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return HttpResponse('Tenant not found', status=404)
    ctx = _order_doc_context(pk, tenant)

    # Server-side PDF via WeasyPrint
    html_string = render_to_string('orders/docs/shipping_label.html', ctx, request=request)
    from weasyprint import HTML, CSS
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    order = ctx['order']
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="shipping-label-{order.order_number}.pdf"'
    return response


# ─────────────────────────────────────────────────────────
# Referred-by client search (HTMX)
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def referred_by_search(request):
    """Returns a small list of matching clients for the referred_by field."""
    try:
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return HttpResponse("")
        q = (request.GET.get("referred_q") or request.GET.get("referred_q_modal") or "").strip()
        if not q or len(q) < 2:
            return HttpResponse("")
        clients = (
            Client.objects.filter(is_active=True)
            .filter(Q(name__icontains=q) | Q(phone__icontains=q))
            .order_by("name")[:10]
        )
        return render(request, "orders/partials/_referred_by_results.html",
                      {"clients": clients})
    except Exception as e:
        return HttpResponse(
            f'<div class="text-danger small p-2">Search error: {type(e).__name__}: {e}</div>'
        )


# ─────────────────────────────────────────────────────────
# Status Board — public display for second monitor
# ─────────────────────────────────────────────────────────
def status_board(request):
    """
    No login required. Protected by DISPLAY_KEY from .env.
    Auto-refreshes every 60s.
    """
    from django.conf import settings as dj_settings
    from datetime import date as _date2, timedelta as _td2
    from django.db import models

    display_key = getattr(request, 'tenant', None) and request.tenant.display_key or getattr(dj_settings, 'DISPLAY_KEY', '')
    if display_key and request.GET.get('key') != display_key:
        return HttpResponse(
            '''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{font-family:sans-serif;background:#0f1117;color:#aaa;
       display:flex;align-items:center;justify-content:center;
       height:100vh;margin:0;flex-direction:column;gap:12px}
  .lock{font-size:48px}
  h2{color:#fff;margin:0;font-size:1.2rem}
  code{background:#1a1d27;padding:4px 12px;border-radius:6px;
       color:#4f8ef7;font-size:0.9rem}
</style></head>
<body>
  <div class="lock">🔒</div>
  <h2>Status Board</h2>
  <p style="margin:0">Add the access key to the URL:</p>
  <code>yourdomain.com/display/?key=YOUR_KEY</code>
</body></html>''',
            status=403, content_type='text/html',
        )

    # Get tenant from subdomain or first tenant as fallback
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        from .models import Tenant
        tenant = Tenant.objects.first()
    if not tenant:
        return HttpResponse("No tenant configured", status=404)

    today    = _date2.today()
    tomorrow = today + _td2(days=1)

    # Base queryset
    orders = (
        Order.objects
        .filter(tenant=tenant)
        .exclude(status__in=['canceled', 'delivered'])
        .select_related('client')
        .prefetch_related(
            'items__product_type',
            'staff_assignments__user',
        )
        .order_by('fitting_time', 'fitting_date')
    )

    # Today's fittings — earlier time first, null times last
    fittings_today = orders.filter(
        fitting_date=today
    ).order_by(
        models.F('fitting_time').asc(nulls_last=True)
    )

    # Ready for pickup — earlier ready time first
    ready_orders = orders.filter(status='ready').order_by(
        'ready_date',
        models.F('ready_time').asc(nulls_last=True)
    )

    # Departing today or tomorrow — by date then time
    departing = (
        Order.objects
        .filter(tenant=tenant)
        .exclude(status__in=['canceled', 'delivered'])
        .filter(departure_date__in=[today, tomorrow])
        .select_related('client')
        .prefetch_related('items__product_type', 'staff_assignments__user')
        .order_by('departure_date', models.F('fitting_time').asc(nulls_last=True))
    )

    # In progress — by ready date then time
    in_progress = orders.filter(
        status__in=['processing', 'alterations', 'pending']
    ).order_by(
        models.F('ready_date').asc(nulls_last=True),
        models.F('ready_time').asc(nulls_last=True)
    )

    # Urgent orders — by departure date, then fitting date/time
    urgent = orders.filter(is_urgent=True).order_by(
        models.F('departure_date').asc(nulls_last=True),
        models.F('fitting_date').asc(nulls_last=True),
        models.F('fitting_time').asc(nulls_last=True)
    )

    # Shipping — orders with ship delivery type, ordered by delivery_date
    from .models import Delivery
    shipping_orders = (
        Order.objects
        .filter(tenant=tenant)
        .exclude(status__in=['canceled', 'delivered'])
        .filter(delivery__type='ship')
        .select_related('client', 'delivery')
        .prefetch_related('items__product_type', 'staff_assignments__user')
        .order_by(
            models.F('delivery_date').asc(nulls_last=True),
            models.F('delivery_time').asc(nulls_last=True)
        )
    )

    return render(request, 'orders/status_board.html', {
        'tenant':          tenant,
        'today':           today,
        'tomorrow':        tomorrow,
        'fittings_today':  fittings_today,
        'ready_orders':    ready_orders,
        'departing':       departing,
        'in_progress':     in_progress,
        'urgent':          urgent,
        'shipping_orders': shipping_orders,
    })


# ─────────────────────────────────────────────────────────────────
# Sales Report
# ─────────────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def sales_report(request):
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    import datetime

    tenant = getattr(request, "tenant", None)

    # ── Date filter ───────────────────────────────────────────────
    period     = request.GET.get('period', 'this_month')
    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')
    today      = timezone.now().date()

    if period == 'today':
        start = today
        end   = today
    elif period == 'this_week':
        start = today - datetime.timedelta(days=today.weekday())
        end   = today
    elif period == 'this_month':
        start = today.replace(day=1)
        end   = today
    elif period == 'last_month':
        first = today.replace(day=1)
        end   = first - datetime.timedelta(days=1)
        start = end.replace(day=1)
    elif period == 'this_year':
        start = today.replace(month=1, day=1)
        end   = today
    elif period == 'custom' and date_from and date_to:
        try:
            start = datetime.date.fromisoformat(date_from)
            end   = datetime.date.fromisoformat(date_to)
        except ValueError:
            start = today.replace(day=1)
            end   = today
    else:
        start = today.replace(day=1)
        end   = today

    # ── Payments in period ────────────────────────────────────────
    from .models import Payment, OrderStaff
    payments_qs = Payment.objects.filter(
        order__tenant=tenant,
        created_at__date__gte=start,
        created_at__date__lte=end,
        original_amount__gt=0,   # exclude refunds
    ).select_related('order', 'order__client')

    # ── Shop totals ───────────────────────────────────────────────
    shop_total    = payments_qs.aggregate(t=Sum('thb_equivalent'))['t'] or 0
    order_ids     = payments_qs.values_list('order_id', flat=True).distinct()
    order_count   = order_ids.count()

    # ── Per-staff breakdown ───────────────────────────────────────
    staff_rows = []
    assignments = (
        OrderStaff.objects
        .filter(order__tenant=tenant, order_id__in=order_ids)
        .select_related('user', 'user__staff_profile', 'order')
        .order_by('user__username')
    )

    # Group by staff member
    staff_map = {}
    for a in assignments:
        uid = a.user_id
        if uid not in staff_map:
            staff_map[uid] = {
                'name':    a.user.get_full_name() or a.user.username,
                'role':    a.get_role_display(),
                'orders':  set(),
                'sales':   0,
                'default_commission': float(
                    getattr(getattr(a.user, 'staff_profile', None),
                            'default_commission_percentage', 0) or 0
                ),
            }
        staff_map[uid]['orders'].add(a.order_id)
        # Sum payments for this staff member's orders within the period
        staff_payments = payments_qs.filter(order=a.order).aggregate(
            t=Sum('thb_equivalent')
        )['t'] or 0
        staff_map[uid]['sales'] += float(staff_payments)

    for uid, data in staff_map.items():
        data['order_count'] = len(data['orders'])
        data.pop('orders')
        staff_rows.append(data)

    staff_rows.sort(key=lambda x: x['sales'], reverse=True)

    return render(request, 'orders/sales_report.html', {
        'period':       period,
        'date_from':    date_from or start.isoformat(),
        'date_to':      date_to   or end.isoformat(),
        'start':        start,
        'end':          end,
        'shop_total':   shop_total,
        'order_count':  order_count,
        'staff_rows':   staff_rows,
        'today':        today,
    })


# ─────────────────────────────────────────────────────────────────
# PWA Service Worker — served at /sw.js (root scope required)
# ─────────────────────────────────────────────────────────────────
from django.http import HttpResponse
from django.views.decorators.cache import cache_control

@cache_control(no_cache=True)
def service_worker(request):
    import os
    from django.contrib.staticfiles import finders
    path = finders.find('sw.js')
    if path and os.path.exists(path):
        with open(path, 'r') as f:
            content = f.read()
    else:
        content = "self.addEventListener('fetch', e => {});"
    return HttpResponse(content, content_type='application/javascript')


# ─────────────────────────────────────────────────────────
# QR Code Generator
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def qr_generator(request):
    """QR code generator — creates catalogue URLs with staff ref + category tracking."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    staff_list = User.objects.filter(
        is_staff=True, is_active=True, is_superuser=False
    ).order_by('first_name')

    # Fetch categories from fashion_01 API
    categories = []
    try:
        import httpx
        r = httpx.get(
            "https://emporiumarmani.com/api/v1/categories/",
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                categories = data[0].get('categories', [])
    except Exception:
        pass

    return render(request, "orders/qr_generator.html", {
        "staff_list": staff_list,
        "categories": categories,
    })


# ─────────────────────────────────────────────────────────
# Production Bill — Public Share View (no login required)
# ─────────────────────────────────────────────────────────
def production_bill_share(request, token):
    """Public view for production bill — accessible via share token, no login needed."""
    from orders.models import ProductionBill
    bill = get_object_or_404(
        ProductionBill.objects
        .select_related(
            "order_item__order__client",
            "order_item__order__signature",
            "order_item__product_type",
            "order_item__measurement",
            "confirmed_by",
            "created_by",
        )
        .prefetch_related(
            "style_selections__variation_type",
            "style_selections__chosen_option",
            "fabric_sets__zone_entries__zone",
            "fabric_sets__monogram__style",
        ),
        share_token=token,
    )

    measurement_fields = _get_measurement_fields(bill.order_item)
    client_photos  = list(bill.order_item.order.client_photos.exclude(image='').order_by('person_number', 'photo_type'))
    item_photos    = list(bill.order_item.photos.exclude(image='').order_by('pk'))
    scratch_notes  = list(bill.order_item.order.scratch_notes.exclude(image='').order_by('created_at'))
    show_signature = request.GET.get("sig", "0") == "1"

    return render(request, "orders/production_bill_print.html", {
        "bill":               bill,
        "order":              bill.order_item.order,
        "item":               bill.order_item,
        "measurement_fields": measurement_fields,
        "fabric_sets":        bill.fabric_sets.all().order_by("piece_number"),
        "style_selections":   bill.style_selections.all().order_by("variation_type__order"),
        "client_photos":      client_photos,
        "item_photos":        item_photos,
        "scratch_notes":      scratch_notes,
        "show_signature":     show_signature,
        "share_view":         True,
    })


# ─────────────────────────────────────────────────────────
# Tailor Extractor — AI-powered scratch pad extraction
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def extract_contact_view(request):
    """Extract contact info from freeform scratch pad text."""
    if request.method != "POST":
        return HttpResponse(status=405)
    import json as _json
    text = request.POST.get("scratch", "").strip()
    if not text:
        from django.http import JsonResponse
        return JsonResponse({"error": "No text provided"}, status=400)
    try:
        from tailor_extractor import extract_contact
        result = extract_contact(text)
        from django.http import JsonResponse
        return JsonResponse(result)
    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({"error": str(e)}, status=500)


@user_passes_test(staff_check)
def extract_measurements_view(request):
    """Extract body measurements from freeform scratch pad text."""
    if request.method != "POST":
        return HttpResponse(status=405)
    text = request.POST.get("scratch", "").strip()
    gender = request.POST.get("gender", "men").strip()
    if not text:
        from django.http import JsonResponse
        return JsonResponse({"error": "No text provided"}, status=400)
    try:
        from tailor_extractor import extract_measurements
        result = extract_measurements(text)
        from django.http import JsonResponse
        return JsonResponse(result)
    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────────────────
# Scratch Pad Session — AI handwriting extraction
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def scratch_pad_create(request):
    """Staff creates a scratch pad session → returns token + QR URL."""
    if request.method != "POST":
        return HttpResponse(status=405)
    from django.http import JsonResponse
    from orders.models import ScratchPadSession
    mode   = request.POST.get("mode", "contact")
    gender = request.POST.get("gender", "men")
    session = ScratchPadSession.objects.create(mode=mode, gender=gender)
    tablet_url = request.build_absolute_uri(f"/scratch/{session.token}/")
    return JsonResponse({
        "token":      str(session.token),
        "tablet_url": tablet_url,
    })


def scratch_pad_tablet(request, token):
    """Full-screen canvas for client — no login required."""
    from django.http import JsonResponse
    from orders.models import ScratchPadSession
    session = get_object_or_404(ScratchPadSession, token=token)
    if session.is_expired:
        return HttpResponse("<h2>This scratch pad has expired. Please ask staff for a new one.</h2>", status=410)
    return render(request, "orders/scratch_pad_tablet.html", {"session": session})


def scratch_pad_submit(request, token):
    """Client submits canvas image → Gemini reads it → saves result."""
    from django.http import JsonResponse
    from orders.models import ScratchPadSession
    session = get_object_or_404(ScratchPadSession, token=token)
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    if session.is_expired:
        return JsonResponse({"error": "Session expired"}, status=410)

    image_data = request.POST.get("image", "")
    if not image_data:
        return JsonResponse({"error": "No image data"}, status=400)

    try:
        if session.mode == "contact":
            from tailor_extractor.vision import extract_contact_from_image
            result = extract_contact_from_image(image_data)
        else:
            from tailor_extractor.vision import extract_measurements_from_image
            result = extract_measurements_from_image(image_data)

        if "_error" in result:
            return JsonResponse({"success": False, "error": result["_error"]})

        session.result = result
        session.status = "processed"
        session.save(update_fields=["result", "status"])
        return JsonResponse({"success": True, "result": result})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@user_passes_test(staff_check)
def scratch_pad_poll(request, token):
    """Staff polls for result — returns status + result when ready."""
    from django.http import JsonResponse
    from orders.models import ScratchPadSession
    session = get_object_or_404(ScratchPadSession, token=token)
    if session.is_expired and session.status == "pending":
        return JsonResponse({"status": "expired"})
    return JsonResponse({
        "status": session.status,
        "result": session.result if session.status == "processed" else {},
    })

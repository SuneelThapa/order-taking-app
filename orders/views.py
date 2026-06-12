# orders/views.py
import base64
import json
import uuid

from django.shortcuts import render, redirect, get_object_or_404
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
)
from .forms import (
    ClientForm, OrderForm, OrderItemFormSet,
    ClientPhotoFormSet, DeliveryForm,
    PaymentForm, PaymentCreateFormSet,
    OrderStaffFormSet, get_measurement_form,
    CancellationForm,
    ClientEditForm,
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
    status = request.GET.get("status") or ""
    q      = (request.GET.get("q") or "").strip()
    sort   = request.GET.get("sort") or "-created_at"
    if sort not in _ALLOWED_SORTS:
        sort = "-created_at"
    page = request.GET.get("page", 1)

    orders = Order.objects.filter(tenant=tenant).select_related("client")
    if status:
        orders = orders.filter(status=status)
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q)
            | Q(client__name__icontains=q)
            | Q(client__phone__icontains=q)
            | Q(client__email__icontains=q)
        )

    paginator = Paginator(orders.order_by(sort), 10)
    return {"page_obj": paginator.get_page(page),
            "current_status": status, "current_sort": sort, "current_q": q}


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
        Order.objects.select_related("client", "delivery")
        .prefetch_related(
            "client_photos", "scratch_notes", "payments",
            "staff_assignments__user", "items__photos", "items__measurement",
        ).filter(tenant=tenant),
        pk=pk,
    )
    return render(request, "orders/_order_detail.html", {"selected_order": order})


@user_passes_test(staff_check)
def order_delete(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    if request.method != "DELETE":
        return HttpResponse(status=405)
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
        # HX-Trigger fires on the (now-detached) button element — unreliable after outerHTML swap.
        # Add explicit headers so htmx:afterRequest (dispatched on document.body) can read them.
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
# Payment row (HTMX "Add payment")
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

    # Canceled orders cannot be edited — use Cancel order button flow
    if edit_order and edit_order.status == "canceled":
        messages.error(request, f"Order #{edit_order.order_number} is canceled and cannot be edited.")
        return redirect("orders:dashboard")
    existing_delivery = getattr(edit_order, "delivery", None) if edit_order else None

    if request.method == "POST":
        order_form           = OrderForm(request.POST, instance=edit_order,
                                         user=request.user, tenant=tenant)
        item_formset         = OrderItemFormSet(request.POST, request.FILES, instance=edit_order)
        client_photo_formset = ClientPhotoFormSet(request.POST, request.FILES,
                                                   instance=edit_order, prefix="client_photos")
        staff_formset        = OrderStaffFormSet(request.POST, instance=edit_order, prefix="staff")
        delivery_form        = DeliveryForm(request.POST, instance=existing_delivery, prefix="delivery")
        payment_formset      = PaymentCreateFormSet(request.POST, prefix="payments")

        # ── Validate client first ─────────────────────────
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

        # ── Validate the rest of the forms ────────────────
        core_valid = (
            client_obj is not None          # client must be resolved
            and order_form.is_valid()
            and item_formset.is_valid()
            and client_photo_formset.is_valid()
            and staff_formset.is_valid()
            and delivery_form.is_valid()
        )
        # Payments are optional — validate separately; never block the main save.
        # We save only payment forms that have an actual amount.
        payment_formset.is_valid()  # run validation so cleaned_data is populated
        all_valid = core_valid

        if all_valid:
            # ── Order ──────────────────────────────────────────
            order        = order_form.save(commit=False)
            order.tenant = tenant
            # client_obj was validated above; set it on the order
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

            # ── Delivery ───────────────────────────────────────
            delivery       = delivery_form.save(commit=False)
            delivery.order = order
            delivery.save()

            # ── Scratch canvas ─────────────────────────────────
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

            # ── Client photos ──────────────────────────────────
            client_photo_formset.instance = order
            client_photo_formset.save()

            # ── Items + measurements + photos ──────────────────
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

                for uploaded in request.FILES.getlist(f"item_photos_{form.prefix}"):
                    OrderItemPhoto.objects.create(order_item=item, image=uploaded)
                for del_id in request.POST.getlist(f"delete_item_photos_{form.prefix}"):
                    OrderItemPhoto.objects.filter(id=del_id, order_item=item).delete()

                if item.product_type_id:
                    model  = apps.get_model("orders", item.product_type.measurement_model)
                    base, _ = BaseMeasurement.objects.get_or_create(order_item=item)
                    MForm  = modelform_factory(model, exclude=("base",))
                    m_inst = model.objects.filter(base=base).first()
                    mform  = MForm(request.POST, instance=m_inst, prefix=f"measure-{form.prefix}")
                    if getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                        for fld in mform.fields.values():
                            fld.disabled = True
                    if mform.is_valid():
                        m = mform.save(commit=False)
                        m.base = base
                        m.save()

            for form in item_formset.deleted_forms:
                if form.instance.pk:
                    form.instance.delete()

            # Use manually entered total_amount if provided, otherwise calc from items
            manual_total = order_form.cleaned_data.get("total_amount")
            order.total_amount = manual_total if manual_total else total
            order.save()

            # ── Staff assignments ──────────────────────────────
            print(f"DEBUG: Starting staff save for order {order.pk}")
            staff_formset.instance = order
            for form in staff_formset.forms:
                if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                    continue
                try:
                    assignment       = form.save(commit=False)
                    assignment.order = order
                    # Default commission from StaffProfile, fall back to 0
                    try:
                        assignment.commission_percentage = (
                            assignment.user.staff_profile.default_commission_percentage
                        )
                    except Exception:
                        assignment.commission_percentage = 0
                    print(f"DEBUG: Saving staff {assignment.user_id} commission={assignment.commission_percentage}")
                    assignment.save()
                    print(f"DEBUG: Staff saved OK pk={assignment.pk}")
                except Exception as _staff_err:
                    print(f"DEBUG: Staff save ERROR: {type(_staff_err).__name__}: {_staff_err}")
            for form in staff_formset.deleted_forms:
                if form.instance.pk:
                    form.instance.delete()

            # ── Payments (multiple) ────────────────────────────
            print(f"DEBUG payments: {len(payment_formset.forms)} forms")
            for form in payment_formset.forms:
                cd = getattr(form, 'cleaned_data', None)
                if not cd:
                    print(f"DEBUG payment skip: no cleaned_data prefix={form.prefix}")
                    continue
                if cd.get("DELETE"):
                    continue
                amount = cd.get("original_amount")
                if not amount:
                    print(f"DEBUG payment skip: no amount prefix={form.prefix}")
                    continue
                print(f"DEBUG payment: prefix={form.prefix} amount={amount} type={cd.get('type')} valid={form.is_valid()} errors={form.errors}")
                try:
                    # Build Payment directly so choices issues don't block save
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
                    print(f"DEBUG payment saved: pk={payment.pk} thb={payment.thb_equivalent}")
                except Exception as _pay_err:
                    print(f"DEBUG payment ERROR: {type(_pay_err).__name__}: {_pay_err}")

            # ── Client signature ───────────────────────────────
            print(f"DEBUG: Starting signature save for order {order.pk}")
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
        client_photo_formset = ClientPhotoFormSet(instance=edit_order, prefix="client_photos")
        staff_formset        = OrderStaffFormSet(instance=edit_order, prefix="staff")
        delivery_form        = DeliveryForm(instance=existing_delivery, prefix="delivery")
        payment_formset      = PaymentCreateFormSet(prefix="payments")

    # Build item rows
    post = request.POST if request.method == "POST" else None
    item_rows = []
    for form in item_formset.forms:
        item = form.instance
        existing_photos  = list(item.photos.all()) if item.pk else []
        measurement_form = None
        if item.pk and item.product_type_id:
            model  = apps.get_model("orders", item.product_type.measurement_model)
            base   = BaseMeasurement.objects.filter(order_item=item).first()
            m_inst = model.objects.filter(base=base).first() if base else None
            MForm  = modelform_factory(model, exclude=("base",))
            measurement_form = MForm(post, instance=m_inst, prefix=f"measure-{form.prefix}")
            if getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                for fld in measurement_form.fields.values():
                    fld.disabled = True
        item_rows.append({"form": form, "measurement_form": measurement_form,
                          "existing_photos": existing_photos})

    # Restore selected client on error
    selected_client = None
    if edit_order:
        selected_client = edit_order.client
    elif request.method == "POST":
        cid = request.POST.get("client")
        if cid:
            selected_client = Client.objects.filter(pk=cid).first()

    # Determine which step has the first error (for auto-navigation).
    # Use any() so that [{}] / [{}, {}, {}] (valid empty forms) don't count as errors.
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
        elif any(
            f.errors for f in payment_formset.forms
            if getattr(f, 'cleaned_data', None) and f.cleaned_data.get('original_amount')
        ):
            first_error_step = 6

    context = {
        "is_edit":              is_edit,
        "edit_order":           edit_order,
        "order_form":           order_form,
        "item_formset":         item_formset,
        "item_rows":            item_rows,
        "client_photo_formset": client_photo_formset,
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
        "item_form": form, "measurement_form": None,
        "existing_photos": [], "is_new": True,
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
def _get_measurement_fields(item):
    """Return [(label, value), …] for the item's linked measurement record."""
    try:
        base  = item.measurement          # BaseMeasurement OneToOne
        model = apps.get_model("orders", item.product_type.measurement_model)
        m     = model.objects.filter(base=base).first()
        if not m:
            return []
        fields = []
        for f in m._meta.get_fields():
            if f.name in ("id", "base") or f.is_relation:
                continue
            val = getattr(m, f.name, None)
            if val not in (None, "", 0):
                fields.append((f.verbose_name.title(), val))
        return fields
    except Exception:
        return []


# ─────────────────────────────────────────────────────────
# Order detail modal
# ─────────────────────────────────────────────────────────
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

    # Build measurement data per item — lazy access with full exception guards
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

    # Existing signature
    try:
        signature = order.signature
    except Exception:
        signature = None

    try:
        payments = list(order.payments.select_related("recorded_by").all())
    except Exception as _e:
        print(f"DEBUG order_detail payments error: {_e}")
        payments = []

    context = {
        "order":                   order,
        "items_with_measurements": items_with_measurements,
        "payments":                payments,
        "signature":               signature,
        "status_choices":          Order.STATUS_CHOICES,
        "quick_pay_form":          PaymentForm(prefix="qp"),
    }
    print(f"DEBUG order_detail: rendering for order {order.pk}, {len(items_with_measurements)} items, {len(payments)} payments")
    return render(request, "orders/partials/_order_detail_modal.html", context)


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

    # Return updated select so it reflects the saved value
    response = render(request, "orders/partials/_status_select.html",
                      {"order": order, "status_choices": Order.STATUS_CHOICES})
    response["HX-Trigger"] = json.dumps({
        "statusChanged": {"orderId": order.pk, "status": order.status}
    })
    return response


# ─────────────────────────────────────────────────────────
# Add payment (from order detail modal)
# ─────────────────────────────────────────────────────────
@user_passes_test(staff_check)
def order_add_payment(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    if request.method != "POST":
        return HttpResponse(status=405)

    form = PaymentForm(request.POST, prefix="qp")
    # Make original_amount required for this inline form
    form.fields["original_amount"].required = True

    if form.is_valid():
        cd       = form.cleaned_data
        ptype    = cd.get("type") or "deposit"

        # ── Refund guard ───────────────────────────────────────────
        # Block negative amounts AND explicit Refund type unless owner approved
        amount = cd.get("original_amount")
        if ptype == "refund" or (amount is not None and amount < 0):
            approved = False
            try:
                record = order.cancellation
                approved = bool(record.approved_by_id)
                print(f"DEBUG refund guard: order={order.pk} "
                      f"record={record.pk} approved_by_id={record.approved_by_id}")
            except Exception as e:
                print(f"DEBUG refund guard: no cancellation_record for order {order.pk}: {e}")

            if not approved:
                return render(request, "orders/partials/_payment_history.html",
                              {"order": order,
                               "payments": order.payments.select_related("recorded_by").all(),
                               "quick_pay_form": PaymentForm(prefix="qp"),
                               "pay_form_error": "Refund not allowed — "
                                                 "owner must approve the cancellation first."})
        # ───────────────────────────────────────────────────────────

        Payment.objects.create(
            order                = order,
            recorded_by          = request.user,
            original_amount      = cd["original_amount"],
            currency             = cd.get("currency")             or "THB",
            exchange_rate_to_thb = cd.get("exchange_rate_to_thb") or 1,
            method               = cd.get("method")               or "cash",
            type                 = ptype,
            notes                = cd.get("notes")                or "",
        )
        payments = order.payments.select_related("recorded_by").all()
        response = render(request, "orders/partials/_payment_history.html",
                          {"order": order, "payments": payments,
                           "quick_pay_form": PaymentForm(prefix="qp")})
        response["HX-Trigger"] = json.dumps({"paymentAdded": True})
        return response

    # Return form with validation errors
    print(f"DEBUG add_payment form invalid for order {pk}: {dict(form.errors)}")
    print(f"DEBUG add_payment POST: { {k:v for k,v in request.POST.items() if 'csrf' not in k} }")
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

    # Already canceled — show info only
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
        form = CancellationForm()
        return render(request, "orders/partials/_cancel_form.html", {
            "order": order,
            "form":  form,
        })

    # POST — process cancellation
    form = CancellationForm(request.POST)
    if not form.is_valid():
        print(f"DEBUG cancel form errors for order {pk}: {dict(form.errors)}")
        print(f"DEBUG POST data: { {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'} }")
        # HX-Retarget overrides hx-swap="none" so validation errors are shown in modal
        response = render(request, "orders/partials/_cancel_form.html", {
            "order": order,
            "form":  form,
        })
        response["HX-Retarget"] = "#cancel-modal-body"
        response["HX-Reswap"]   = "innerHTML"
        return response

    cancellation              = form.save(commit=False)
    cancellation.order        = order
    cancellation.canceled_by  = request.user
    cancellation.save()

    order.status = "canceled"
    order.save()
    cache.delete(f"order_status_counts_{tenant.id}")

    # hx-swap="none" keeps the button in the DOM so HX-Trigger bubbles correctly
    response = HttpResponse("")
    response["HX-Trigger"] = json.dumps({
        "orderCanceled": {"pk": order.pk, "orderNumber": order.order_number},
    })
    return response


# ─────────────────────────────────────────────────────────
# Owner: approve or reject a partial refund
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
        cancellation.resolution      = "none"
        cancellation.resolution_notes = (
            (cancellation.resolution_notes or "") +
            f"\n[Rejected by {request.user.username}]"
        ).strip()
        cancellation.save()

    # Return updated approvals banner
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
# Pending approvals — refreshed from dashboard JS
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

    # Return with errors — HX-Retarget overrides hx-swap="none" to show them
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
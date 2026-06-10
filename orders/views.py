# orders/views.py
import base64
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

from orders.models import Order, ProductType, BaseMeasurement, OrderItemPhoto
from .models import ScratchNote
from .forms import (
    OrderForm,
    OrderItemForm,
    OrderItemFormSet,
    ClientPhotoFormSet,
    get_measurement_form,
)


def staff_check(user):
    return user.is_staff


# =====================================================
# Shared helpers
# =====================================================
def _get_counts(tenant):
    key = f"order_status_counts_{tenant.id}"
    counts = cache.get(key)
    if counts is None:
        counts = {
            "new": Order.objects.filter(status="new", tenant=tenant).count(),
            "pending": Order.objects.filter(status="pending", tenant=tenant).count(),
            "in_progress": Order.objects.filter(status="in_progress", tenant=tenant).count(),
            "ready": Order.objects.filter(status="ready", tenant=tenant).count(),
            "delivered": Order.objects.filter(status="delivered", tenant=tenant).count(),
        }
        cache.set(key, counts, 60)
    return counts


def _build_cards(counts):
    return [
        {"status": "new",         "label": "New",         "css": "c-new",       "icon": "bi-inbox",           "count": counts["new"]},
        {"status": "pending",     "label": "Pending",     "css": "c-pending",   "icon": "bi-hourglass-split", "count": counts["pending"]},
        {"status": "in_progress", "label": "In progress", "css": "c-progress",  "icon": "bi-gear",            "count": counts["in_progress"]},
        {"status": "ready",       "label": "Ready",        "css": "c-ready",     "icon": "bi-check2-circle",   "count": counts["ready"]},
        {"status": "delivered",   "label": "Delivered",    "css": "c-delivered", "icon": "bi-truck",           "count": counts["delivered"]},
    ]


_ALLOWED_SORTS = {
    "order_number", "-order_number", "status", "-status",
    "total_amount", "-total_amount", "created_at", "-created_at",
}


def _orders_table_context(request, tenant):
    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()
    sort = request.GET.get("sort") or "-created_at"
    if sort not in _ALLOWED_SORTS:
        sort = "-created_at"
    page = request.GET.get("page", 1)

    orders = Order.objects.filter(tenant=tenant)
    if status:
        orders = orders.filter(status=status)
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q)
        )

    paginator = Paginator(orders.order_by(sort), 10)
    page_obj = paginator.get_page(page)
    return {"page_obj": page_obj, "current_status": status, "current_sort": sort, "current_q": q}


# =====================================================
# DASHBOARD / CARDS / TABLE / DETAIL / DELETE
# =====================================================
@user_passes_test(staff_check)
def dashboard(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    return render(request, "admin_dashboard/dashboard.html", {"cards": _build_cards(_get_counts(tenant))})


@user_passes_test(staff_check)
def stat_cards(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    return render(request, "admin_dashboard/partials/_stat_cards.html", {"cards": _build_cards(_get_counts(tenant))})


@user_passes_test(staff_check)
def orders_table(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    return render(request, "admin_dashboard/partials/orders_table.html", _orders_table_context(request, tenant))


@user_passes_test(staff_check)
def order_detail(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    selected_order = get_object_or_404(
        Order.objects.prefetch_related(
            "client_photos", "scratch_notes", "items__photos", "items__measurement"
        ).filter(tenant=tenant),
        pk=pk,
    )
    return render(request, "orders/_order_detail.html", {"selected_order": selected_order})


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

    context = _orders_table_context(request, tenant)
    context["oob_cards"] = True
    context["cards"] = _build_cards(_get_counts(tenant))
    return render(request, "admin_dashboard/partials/orders_table.html", context)


# =====================================================
# ADD / EDIT ORDER  — wizard, single POST
# =====================================================
@user_passes_test(staff_check)
def order_form_view(request, pk=None):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    show_edit_form = pk is not None
    edit_order = get_object_or_404(Order, pk=pk, tenant=tenant) if show_edit_form else None

    if request.method == "POST":
        order_form = OrderForm(request.POST, instance=edit_order, user=request.user, tenant=tenant)
        item_formset = OrderItemFormSet(request.POST, request.FILES, instance=edit_order)
        client_photo_formset = ClientPhotoFormSet(
            request.POST, request.FILES, instance=edit_order, prefix="client_photos"
        )

        if order_form.is_valid() and item_formset.is_valid() and client_photo_formset.is_valid():
            order = order_form.save(commit=False)
            order.tenant = tenant

            model_default_status = Order._meta.get_field("status").get_default()
            if getattr(request.user, "is_tenant", False) and request.user.is_staff:
                status_value = order_form.cleaned_data.get("status_hidden") or model_default_status
                order.status = status_value.lower()
            elif getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                order.status = model_default_status

            if not show_edit_form:
                order.total_amount = 0
            order.save()
            cache.delete(f"order_status_counts_{tenant.id}")

            # Scratch canvas
            canvas_data = request.POST.get("scratch_canvas_image")
            if canvas_data:
                try:
                    fmt, imgstr = canvas_data.split(";base64,")
                    ext = fmt.split("/")[-1]
                    file = ContentFile(base64.b64decode(imgstr), name=f"scratch_{uuid.uuid4()}.{ext}")
                    ScratchNote.objects.create(order=order, image=file)
                except Exception:
                    pass

            # Client photos (3 fixed slots)
            client_photo_formset.instance = order
            client_photo_formset.save()

            # Items + measurements + photos
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

                # Item photos via a single multiple-file input named item_photos_<prefix>
                for uploaded in request.FILES.getlist(f"item_photos_{form.prefix}"):
                    OrderItemPhoto.objects.create(order_item=item, image=uploaded)

                # Existing photo deletions
                delete_ids = request.POST.getlist(f"delete_item_photos_{form.prefix}")
                if delete_ids:
                    OrderItemPhoto.objects.filter(id__in=delete_ids, order_item=item).delete()

                # Measurement
                if item.product_type:
                    model = apps.get_model("orders", item.product_type.measurement_model)
                    base, _ = BaseMeasurement.objects.get_or_create(order_item=item)
                    MeasurementForm = modelform_factory(model, exclude=("base",))
                    measurement_instance = model.objects.filter(base=base).first()
                    measurement_form = MeasurementForm(
                        request.POST, instance=measurement_instance, prefix=f"measure-{form.prefix}"
                    )
                    if getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                        for fld in measurement_form.fields.values():
                            fld.disabled = True
                    if measurement_form.is_valid():
                        m = measurement_form.save(commit=False)
                        m.base = base
                        m.save()

            for obj in item_formset.deleted_objects:
                obj.delete()

            order.total_amount = total
            order.save()

            messages.success(request, f"Order #{order.order_number} saved.")
            return redirect("orders:dashboard")
        # invalid -> fall through and re-render with errors
    else:
        initial_data = {}
        if not show_edit_form:
            initial_data["status_hidden"] = Order._meta.get_field("status").get_default()
        order_form = OrderForm(instance=edit_order, user=request.user, tenant=tenant, initial=initial_data)
        item_formset = OrderItemFormSet(instance=edit_order)
        client_photo_formset = ClientPhotoFormSet(instance=edit_order, prefix="client_photos")

    # Build per-item rows: (form, measurement_form, existing_photos)
    post = request.POST if request.method == "POST" else None
    item_rows = []
    for form in item_formset.forms:
        item = form.instance
        existing_photos = list(item.photos.all()) if item.pk else []
        measurement_form = None
        if item.pk and item.product_type_id:
            model = apps.get_model("orders", item.product_type.measurement_model)
            base = BaseMeasurement.objects.filter(order_item=item).first()
            measurement_instance = model.objects.filter(base=base).first() if base else None
            MeasurementForm = modelform_factory(model, exclude=("base",))
            measurement_form = MeasurementForm(post, instance=measurement_instance, prefix=f"measure-{form.prefix}")
            if getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                for fld in measurement_form.fields.values():
                    fld.disabled = True
        item_rows.append({"form": form, "measurement_form": measurement_form, "existing_photos": existing_photos})

    context = {
        "show_edit_form": show_edit_form,
        "edit_order": edit_order,
        "order_form": order_form,
        "item_formset": item_formset,
        "item_rows": item_rows,
        "client_photo_formset": client_photo_formset,
    }
    return render(request, "orders/order_form.html", context)


# =====================================================
# BLANK ITEM ROW (htmx "Add item")
# =====================================================
@user_passes_test(staff_check)
def order_item_row(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    try:
        index = int(request.GET.get("index", 0))
    except (TypeError, ValueError):
        index = 0

    item_form = OrderItemForm(prefix=f"items-{index}")
    return render(
        request,
        "orders/partials/_order_item_row.html",
        {"item_form": item_form, "measurement_form": None, "existing_photos": [], "is_new": True},
    )


# =====================================================
# LOAD MEASUREMENT FORM (htmx, on product_type change)
# =====================================================
def load_measurement_form(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    product_type_id = request.GET.get("product_type")
    prefix = request.GET.get("prefix")
    if not product_type_id and prefix:
        # hx-include sends the select under its own prefixed name (items-N-product_type)
        product_type_id = request.GET.get(f"{prefix}-product_type")
    if not product_type_id or not prefix:
        return HttpResponse("")  # empty -> clears the container

    cache_key = f"product_type_{product_type_id}"
    product_type = cache.get(cache_key)
    if not product_type:
        product_type = get_object_or_404(ProductType, id=product_type_id)
        cache.set(cache_key, product_type, 300)

    MeasurementForm = get_measurement_form(product_type)
    if not MeasurementForm:
        return HttpResponse("")

    form = MeasurementForm(prefix=f"measure-{prefix}")
    return render(
        request,
        "admin_dashboard/partials/_dynamic_measurement.html",
        {"form": form, "product_type": product_type},
    )
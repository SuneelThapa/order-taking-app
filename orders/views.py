# orders/views.py
from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.core.cache import cache
from django.apps import apps
from django.forms import modelform_factory

from orders.models import Order, ProductType, BaseMeasurement
from .forms import (
    OrderForm,
    OrderItemFormSet,
    OrderItemPhotoFormSet,
    ClientPhotoFormSet,
    get_measurement_form,
)

from .models import ScratchNote

import base64
import uuid
from django.core.files.base import ContentFile


def staff_check(user):
    return user.is_staff


# =====================================================
# DASHBOARD
# =====================================================
@user_passes_test(staff_check)
def dashboard(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    # -------------------------------
    # Cached order counts
    # -------------------------------
    counts = cache.get(f"order_status_counts_{tenant.id}")
    if not counts:
        counts = {
            "new_orders": Order.objects.filter(status="new", tenant=tenant).count(),
            "pending_orders": Order.objects.filter(status="pending", tenant=tenant).count(),
            "in_progress": Order.objects.filter(status="in_progress", tenant=tenant).count(),
            "ready_orders": Order.objects.filter(status="ready", tenant=tenant).count(),
            "delivered_orders": Order.objects.filter(status="delivered", tenant=tenant).count(),
        }
        cache.set(f"order_status_counts_{tenant.id}", counts, 60)

    new_orders = counts["new_orders"]
    pending_orders = counts["pending_orders"]
    in_progress = counts["in_progress"]
    ready_orders = counts["ready_orders"]
    delivered_orders = counts["delivered_orders"]

    show_add_form = request.GET.get("add") == "true"
    edit_order_id = request.GET.get("edit")
    show_edit_form = False
    edit_order = None

    if edit_order_id:
        edit_order = get_object_or_404(Order, pk=edit_order_id, tenant=tenant)
        show_edit_form = True

    # =====================================================
    # POST
    # =====================================================
    if request.method == "POST":
        order_form = OrderForm(
            request.POST,
            instance=edit_order if show_edit_form else None,
            user=request.user,  
            tenant=tenant
        )

        item_formset = OrderItemFormSet(
            request.POST,
            request.FILES,
            instance=edit_order if show_edit_form else None
        )

        client_photo_formset = ClientPhotoFormSet(
            request.POST,
            request.FILES,
            instance=edit_order if show_edit_form else None,
            prefix="client_photos"
        )

        # ---- DEBUGGING HERE ----
        print("POST DATA:", request.POST)
        print("FILES:", request.FILES)
        print("ORDER FORM VALID?", order_form.is_valid())
        if not order_form.is_valid():
            print("ORDER FORM ERRORS:", order_form.errors)
        if not item_formset.is_valid():
            print("ITEM FORMSET ERRORS:", item_formset.errors)
        if not client_photo_formset.is_valid():
            print("CLIENT PHOTO ERRORS:", client_photo_formset.errors)
        # ------------------------

        if order_form.is_valid() and item_formset.is_valid() and client_photo_formset.is_valid():
            order = order_form.save(commit=False)
            order.tenant = tenant

            # --- STATUS HANDLING ---
            # Get model default for status
            model_default_status = Order._meta.get_field("status").get_default()

            # Tenant staff: use hidden field submitted
            if getattr(request.user, "is_tenant", False) and request.user.is_staff:
                status_value = order_form.cleaned_data.get("status_hidden") or model_default_status
                order.status = status_value.lower()

            # Normal tenant (not staff): use model default
            elif getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                order.status = model_default_status

            # Admins: use whatever is in the dropdown (default behavior)

            if not show_edit_form:
                order.total_amount = 0
            order.save()
            
            cache.delete(f"order_status_counts_{tenant.id}")

            # -------------------------------
            # Scratch Note
            # -------------------------------
            canvas_data = request.POST.get("scratch_canvas_image")
            if canvas_data:
                try:
                    fmt, imgstr = canvas_data.split(";base64,")
                    ext = fmt.split("/")[-1]
                    file = ContentFile(
                        base64.b64decode(imgstr),
                        name=f"scratch_{uuid.uuid4()}.{ext}",
                    )
                    ScratchNote.objects.create(order=order, image=file)
                except Exception:
                    pass

            # -------------------------------
            # Client photos
            # -------------------------------
            client_photo_formset.instance = order
            client_photo_formset.save()

            # -------------------------------
            # Items & Measurements
            # -------------------------------
            item_formset.instance = order
            items = item_formset.save(commit=False)
            total = 0

            for form in item_formset.forms:
                if not form.cleaned_data:
                    continue

                item = form.save(commit=False)
                item.order = order
                item.save()
                total += getattr(item, "total_price", 0)

                # Photos
                photo_formset = OrderItemPhotoFormSet(
                    request.POST,
                    request.FILES,
                    instance=item,
                    prefix=f"photos-{form.prefix}",
                )
                if photo_formset.is_valid():
                    photo_formset.save()

                # Measurements
                if item.product_type:
                    model_name = item.product_type.measurement_model
                    model = apps.get_model("orders", model_name)
                    base, _ = BaseMeasurement.objects.get_or_create(order_item=item)

                    MeasurementForm = modelform_factory(model, exclude=("base",))
                    measurement_instance = model.objects.filter(base=base).first()
                    measurement_form = MeasurementForm(
                        request.POST,
                        instance=measurement_instance,
                        prefix=f"measure-{form.prefix}"
                    )

                    # Disable measurement fields for tenant users
                    if getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                        for f in measurement_form.fields.values():
                            f.disabled = True

                    if measurement_form.is_valid():
                        measurement = measurement_form.save(commit=False)
                        measurement.base = base
                        measurement.save()

            for obj in item_formset.deleted_objects:
                obj.delete()

            order.total_amount = total
            order.save()
            return redirect("orders:dashboard")

        show_add_form = True

    # =====================================================
    # GET
    # =====================================================
    else:
        # Pre-fill status_hidden with default for new orders
        initial_data = {}
        if not show_edit_form:
            default_status = Order._meta.get_field("status").get_default()
            initial_data["status_hidden"] = default_status

        order_form = OrderForm(
            request.POST or None,
            instance=edit_order if show_edit_form else None,
            user=request.user,
            tenant=tenant,
            initial=initial_data
        )
        item_formset = OrderItemFormSet(instance=edit_order if show_edit_form else None)
        client_photo_formset = ClientPhotoFormSet(instance=edit_order if show_edit_form else None, prefix="client_photos")

    # =====================================================
    # Build item formsets with photos & measurements
    # =====================================================
    item_forms_with_photos = []
    for form in item_formset.forms:
        item = form.instance

        photo_formset = OrderItemPhotoFormSet(
            request.POST or None,
            request.FILES or None,
            instance=item,
            prefix=f"photos-{form.prefix}",
        )

        measurement_form = None
        if item.pk and item.product_type:
            model = apps.get_model("orders", item.product_type.measurement_model)
            base = BaseMeasurement.objects.filter(order_item=item).first()
            measurement_instance = model.objects.filter(base=base).first() if base else None
            MeasurementForm = modelform_factory(model, exclude=("base",))
            measurement_form = MeasurementForm(
                request.POST or None,
                instance=measurement_instance,
                prefix=f"measure-{form.prefix}"
            )

            # Disable measurement fields for tenant users
            if getattr(request.user, "is_tenant", False) and not request.user.is_staff:
                for f in measurement_form.fields.values():
                    f.disabled = True

        item_forms_with_photos.append((form, photo_formset, measurement_form))

    # =====================================================
    # Order Detail
    # =====================================================
    selected_order = None
    order_id = request.GET.get("order")
    if order_id and not show_add_form and not show_edit_form:
        selected_order = get_object_or_404(
            Order.objects.prefetch_related("client_photos", "items__photos", "items__measurement").filter(tenant=tenant),
            pk=order_id
        )

    context = {
        "new_orders": new_orders,
        "pending_orders": pending_orders,
        "in_progress": in_progress,
        "ready_orders": ready_orders,
        "delivered_orders": delivered_orders,
        "selected_order": selected_order,
        "show_add_form": show_add_form,
        "show_edit_form": show_edit_form,
        "order_form": order_form,
        "item_formset": item_formset,
        "item_forms_with_photos": item_forms_with_photos,
        "client_photo_formset": client_photo_formset,
        "edit_order": edit_order,
    }

    return render(request, "admin_dashboard/dashboard.html", context)


# =====================================================
# ORDERS TABLE
# =====================================================
@user_passes_test(staff_check)
def orders_table(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    status = request.GET.get("status")
    sort = request.GET.get("sort", "-created_at")
    page = request.GET.get("page", 1)

    cache_key = f"orders_table_{tenant.id}_{status}_{sort}_{page}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    orders = Order.objects.filter(tenant=tenant)
    if status:
        orders = orders.filter(status=status)

    orders = orders.order_by(sort)
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(page)

    response = render(request, "admin_dashboard/partials/orders_table.html", {"page_obj": page_obj, "current_sort": sort, "current_status": status})
    #cache.set(cache_key, response, 30)
    return response


# =====================================================
# DELETE ORDER
# =====================================================
@user_passes_test(staff_check)
def order_delete(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    order = get_object_or_404(Order, pk=pk, tenant=tenant)
    if request.method == "DELETE":
        order.delete()
        cache.delete(f"order_status_counts_{tenant.id}")
        return orders_table(request)
    return HttpResponse(status=405)


# =====================================================
# LOAD MEASUREMENT FORM
# =====================================================
def load_measurement_form(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)

    product_type_id = request.GET.get("product_type")
    prefix = request.GET.get("prefix")
    if not product_type_id or not prefix:
        return render(request, "admin_dashboard/partials/_empty.html")

    cache_key = f"product_type_{product_type_id}"
    product_type = cache.get(cache_key)
    if not product_type:
        product_type = get_object_or_404(ProductType, id=product_type_id)
        cache.set(cache_key, product_type, 300)

    MeasurementForm = get_measurement_form(product_type)
    if not MeasurementForm:
        return render(request, "admin_dashboard/partials/_empty.html")

    form = MeasurementForm(prefix=f"measure-{prefix}")
    return render(request, "admin_dashboard/partials/_dynamic_measurement.html", {"form": form, "product_type": product_type})
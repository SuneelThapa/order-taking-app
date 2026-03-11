from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.core.cache import cache

from orders.models import Order, OrderItem, ProductType, BaseMeasurement, ClientPhoto
from .models import ScratchNote

from .forms import (
    OrderForm,
    OrderItemFormSet,
    get_measurement_form,
    OrderItemPhotoFormSet,
    ClientPhotoFormSet,
)

from django.apps import apps
from django.forms import modelform_factory

import base64
import uuid
from django.core.files.base import ContentFile


def staff_check(user):
    return user.is_staff


@user_passes_test(staff_check)
def dashboard(request):

    # ===============================
    # DASHBOARD ORDER COUNTS (Redis Cache)
    # ===============================

    counts = cache.get("dashboard_order_counts")

    if not counts:
        counts = {
            "new": Order.objects.filter(status="new").count(),
            "in_progress": Order.objects.filter(status="in_progress").count(),
            "ready": Order.objects.filter(status="ready").count(),
            "delivered": Order.objects.filter(status="delivered").count(),
            "pending": Order.objects.filter(status="pending").count(),
        }
        cache.set("dashboard_order_counts", counts, 60)

    new_orders = counts["new"]
    in_progress = counts["in_progress"]
    ready_orders = counts["ready"]
    delivered_orders = counts["delivered"]
    pending_orders = counts["pending"]

    show_add_form = request.GET.get("add") == "true"

    edit_order_id = request.GET.get("edit")
    show_edit_form = False
    edit_order = None

    if edit_order_id:
        edit_order = get_object_or_404(Order, pk=edit_order_id)
        show_edit_form = True

    # ===============================
    # POST (CREATE / UPDATE ORDER)
    # ===============================

    if request.method == "POST":

        order_form = OrderForm(request.POST, instance=edit_order) if show_edit_form else OrderForm(request.POST)

        item_formset = (
            OrderItemFormSet(request.POST, request.FILES, instance=edit_order)
            if show_edit_form
            else OrderItemFormSet(request.POST, request.FILES)
        )

        client_photo_formset = (
            ClientPhotoFormSet(request.POST, request.FILES, instance=edit_order, prefix="client_photos")
            if show_edit_form
            else ClientPhotoFormSet(request.POST, request.FILES, prefix="client_photos")
        )

        if order_form.is_valid() and item_formset.is_valid() and client_photo_formset.is_valid():

            # ===============================
            # SAVE ORDER
            # ===============================

            order = order_form.save(commit=False)

            if not show_edit_form:
                order.total_amount = 0

            order.save()

            # ===============================
            # SAVE SCRATCH NOTE (Optimized)
            # ===============================

            canvas_data = request.POST.get("scratch_canvas_image")

            if canvas_data and canvas_data.startswith("data:image") and len(canvas_data) > 1000:

                try:
                    header, imgstr = canvas_data.split(";base64,")
                    ext = header.split("/")[-1]

                    image_file = ContentFile(
                        base64.b64decode(imgstr),
                        name=f"scratch_{uuid.uuid4()}.{ext}"
                    )

                    ScratchNote.objects.create(
                        order_id=order.id,
                        image=image_file
                    )

                except Exception:
                    pass

            # ===============================
            # SAVE CLIENT PHOTOS
            # ===============================

            client_photo_formset = (
                ClientPhotoFormSet(request.POST, request.FILES, instance=edit_order, prefix="client_photos")
                if show_edit_form
                else ClientPhotoFormSet(request.POST, request.FILES, instance=order, prefix="client_photos")
            )

            if client_photo_formset.is_valid():
                client_photo_formset.save()

            # ===============================
            # SAVE ORDER ITEMS
            # ===============================

            item_formset = (
                OrderItemFormSet(request.POST, request.FILES, instance=edit_order)
                if show_edit_form
                else OrderItemFormSet(request.POST, request.FILES, instance=order)
            )

            if item_formset.is_valid():

                item_formset.save()
                items = item_formset.instance.items.all().order_by("id")

                total = 0

                for index, item in enumerate(items):

                    item.order = order
                    item.save()

                    total += item.total_price
                    form_prefix = item_formset.forms[index].prefix

                    # ===============================
                    # SAVE ITEM PHOTOS
                    # ===============================

                    photo_formset = OrderItemPhotoFormSet(
                        request.POST,
                        request.FILES,
                        instance=item,
                        prefix=f"photos-{form_prefix}"
                    )

                    if photo_formset.is_valid():

                        photos = photo_formset.save(commit=False)

                        for photo in photos:
                            photo.order_item = item
                            photo.save()

                        for obj in photo_formset.deleted_objects:
                            obj.delete()

                    # ===============================
                    # SAVE MEASUREMENTS
                    # ===============================

                    product_type = item.product_type

                    if product_type:

                        model_name = product_type.measurement_model
                        model = apps.get_model("orders", model_name)

                        base, created = BaseMeasurement.objects.get_or_create(order_item=item)

                        MeasurementForm = modelform_factory(model, exclude=("base",))

                        measurement_instance = model.objects.filter(base=base).first()

                        measurement_form = MeasurementForm(
                            request.POST,
                            instance=measurement_instance,
                            prefix=f"measure-{form_prefix}"
                        )

                        if measurement_form.is_valid():

                            measurement = measurement_form.save(commit=False)
                            measurement.base = base
                            measurement.save()

                order.total_amount = total
                order.save()

                # ===============================
                # CLEAR CACHE
                # ===============================

                cache.delete("dashboard_order_counts")
                cache.delete(f"order_detail_{order.id}")

            return redirect("orders:dashboard")

        show_add_form = True

    else:

        if show_edit_form:

            order_form = OrderForm(instance=edit_order)
            item_formset = OrderItemFormSet(instance=edit_order)

            client_photo_formset = ClientPhotoFormSet(
                instance=edit_order,
                prefix="client_photos"
            )

        else:

            order_form = OrderForm()
            item_formset = OrderItemFormSet()

            client_photo_formset = ClientPhotoFormSet(prefix="client_photos")

    # ===============================
    # BUILD ITEM + PHOTO FORMSETS
    # ===============================

    item_forms_with_photos = []

    for form in item_formset.forms:

        item = form.instance

        photo_formset = OrderItemPhotoFormSet(
            request.POST or None,
            request.FILES or None,
            instance=item,
            prefix=f"photos-{form.prefix}"
        )

        measurement_form = None

        if item.pk and item.product_type:

            model_name = item.product_type.measurement_model
            model = apps.get_model("orders", model_name)

            base = BaseMeasurement.objects.filter(order_item=item).first()

            measurement_instance = None
            if base:
                measurement_instance = model.objects.filter(base=base).first()

            MeasurementForm = modelform_factory(model, exclude=("base",))

            measurement_form = MeasurementForm(
                request.POST or None,
                instance=measurement_instance,
                prefix=f"measure-{form.prefix}"
            )

        item_forms_with_photos.append((form, photo_formset, measurement_form))

    # ===============================
    # ORDER DETAIL (Cached)
    # ===============================

    selected_order = None
    order_id = request.GET.get("order")

    if order_id and not show_add_form and not show_edit_form:

        cache_key = f"order_detail_{order_id}"
        selected_order = cache.get(cache_key)

        if not selected_order:

            selected_order = get_object_or_404(
                Order.objects
                .select_related("client")
                .prefetch_related(
                    "client_photos",
                    "items",
                    "items__photos",
                    "scratch_notes"
                ),
                pk=order_id
            )

            cache.set(cache_key, selected_order, 120)

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
    }

    return render(request, "admin_dashboard/dashboard.html", context)


@user_passes_test(staff_check)
def orders_table(request):

    orders = Order.objects.select_related("client").only(
        "id",
        "order_number",
        "status",
        "total_amount",
        "created_at",
        "client"
    )

    status = request.GET.get("status")

    if status:
        orders = orders.filter(status=status)

    sort = request.GET.get("sort", "-created_at")

    allowed_sorts = [
        "order_number",
        "status",
        "total_amount",
        "created_at",
        "-order_number",
        "-status",
        "-total_amount",
        "-created_at",
    ]

    if sort not in allowed_sorts:
        sort = "-created_at"

    orders = orders.order_by(sort)

    paginator = Paginator(orders, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "admin_dashboard/partials/orders_table.html",
        {
            "page_obj": page_obj,
            "current_sort": sort,
            "current_status": status,
        },
    )


@user_passes_test(staff_check)
def order_delete(request, pk):

    order = get_object_or_404(Order, pk=pk)

    if request.method == "DELETE":
        order.delete()

        cache.delete("dashboard_order_counts")
        cache.delete(f"order_detail_{pk}")

        return orders_table(request)

    return HttpResponse(status=405)


def load_measurement_form(request):

    product_type_id = request.GET.get("product_type")
    prefix = request.GET.get("prefix")

    if not product_type_id or not prefix:
        return render(request, "admin_dashboard/partials/_empty.html")

    product_type = get_object_or_404(ProductType, id=product_type_id)

    MeasurementForm = get_measurement_form(product_type)

    if not MeasurementForm:
        return render(request, "admin_dashboard/partials/_empty.html")

    form = MeasurementForm(prefix=f"measure-{prefix}")

    return render(
        request,
        "admin_dashboard/partials/_dynamic_measurement.html",
        {
            "form": form,
            "product_type": product_type,
        },
    )
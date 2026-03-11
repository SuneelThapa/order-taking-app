from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from orders.models import Order, OrderItem, ProductType, BaseMeasurement, ClientPhoto
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .forms import OrderForm, OrderItemFormSet, get_measurement_form, OrderItemPhotoFormSet, ClientPhotoFormSet
from django.apps import apps
from django.forms import modelform_factory

import base64
from django.core.files.base import ContentFile
from .models import ScratchNote


import uuid



def staff_check(user):
    return user.is_staff


@user_passes_test(staff_check)
def dashboard(request):

    # ===============================
    # ORDER COUNTS
    # ===============================

    new_orders = Order.objects.filter(status="new").count()
    in_progress = Order.objects.filter(status="in_progress").count()
    ready_orders = Order.objects.filter(status="ready").count()
    delivered_orders = Order.objects.filter(status="delivered").count()
    pending_orders = Order.objects.filter(status="pending").count()

    show_add_form = request.GET.get("add") == "true"


    edit_order_id = request.GET.get("edit")
    show_edit_form = False
    edit_order = None

    if edit_order_id:
        edit_order = get_object_or_404(Order, pk=edit_order_id)
        show_edit_form = True

    # ===============================
    # POST (CREATE ORDER)
    # ===============================

    if request.method == "POST":

        print("\n========== POST RECEIVED ==========\n")

        if show_edit_form:
            order_form = OrderForm(request.POST, instance=edit_order)
        else:
            order_form = OrderForm(request.POST)

       
        if show_edit_form:
            item_formset = OrderItemFormSet(
                request.POST,
                request.FILES,
                instance=edit_order
            )
        else:
            item_formset = OrderItemFormSet(
                request.POST,
                request.FILES
            )

        # ⚠️ Do NOT pass instance yet
        if show_edit_form:
            client_photo_formset = ClientPhotoFormSet(
                request.POST,
                request.FILES,
                instance=edit_order,
                prefix="client_photos"
            )
        else:
            client_photo_formset = ClientPhotoFormSet(
                request.POST,
                request.FILES,
                prefix="client_photos"
            )

        print("ORDER ERRORS:", order_form.errors)

        print("ORDER VALID:", order_form.is_valid())
        print("ITEM FORMSET VALID:", item_formset.is_valid())
        print("CLIENT PHOTO FORMSET VALID:", client_photo_formset.is_valid())
        print("CLIENT PHOTO ERRORS:", client_photo_formset.errors)
        print("CLIENT PHOTO NON FORM ERRORS:", client_photo_formset.non_form_errors())

        if order_form.is_valid() and item_formset.is_valid() and client_photo_formset.is_valid():



            # ===============================
            # SAVE ORDER
            # ===============================

            order = order_form.save(commit=False)

            if not show_edit_form:
                order.total_amount = 0

            order.save()


            # ===============================
            # SAVE SCRATCH NOTE
            # ===============================

            print("---- SCRATCH DEBUG ----")

            canvas_data = request.POST.get("scratch_canvas_image")

            print("Canvas POST exists:", "scratch_canvas_image" in request.POST)

            if canvas_data:

                print("Canvas data length:", len(canvas_data))
                print("Canvas data preview:", canvas_data[:50])

                try:
                    format, imgstr = canvas_data.split(";base64,")
                    ext = format.split("/")[-1]

                    file = ContentFile(
                        base64.b64decode(imgstr),
                        name=f"scratch_{uuid.uuid4()}.{ext}"
                    )

                    scratch = ScratchNote.objects.create(
                        order=order,
                        image=file
                    )

                    print("✅ SCRATCH NOTE SAVED:", scratch.pk)

                except Exception as e:
                    print("❌ Scratch note save error:", e)

            else:
                print("⚠️ No canvas data received")

            print("------------------------")



            # ===============================
            # SAVE CLIENT PHOTOS
            # ===============================

            if show_edit_form:
                client_photo_formset = ClientPhotoFormSet(
                    request.POST,
                    request.FILES,
                    instance=edit_order,
                    prefix="client_photos"
                )
            else:
                client_photo_formset = ClientPhotoFormSet(
                    request.POST,
                    request.FILES,
                    instance=order,
                    prefix="client_photos"
                )

            if client_photo_formset.is_valid():
                client_photo_formset.save()

            # ===============================
            # SAVE ORDER ITEMS
            # ===============================

            if show_edit_form:
                item_formset = OrderItemFormSet(
                    request.POST,
                    request.FILES,
                    instance=edit_order
                )
            else:
                item_formset = OrderItemFormSet(
                    request.POST,
                    request.FILES,
                    instance=order

                )

            print("REBIND ITEM FORMSET VALID:", item_formset.is_valid())

            if not item_formset.is_valid():
                show_add_form = True
            else:

                item_formset.save()
                items = item_formset.instance.items.all().order_by("id")

                total = 0

                for index, item in enumerate(items):

                    print(f"\n--- Saving Item Index {index} ---")

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

                    

                    # ===============================
                    # SAVE MEASUREMENTS
                    # ===============================

                    product_type = item.product_type
                    print("PRODUCT TYPE:", product_type)

                    if not product_type:
                        print("⚠️ No product type — skipping measurement")
                    else:

                        model_name = product_type.measurement_model
                        print("MEASUREMENT MODEL NAME:", model_name)

                        model = apps.get_model("orders", model_name)

                        base, created = BaseMeasurement.objects.get_or_create(order_item=item)

                        

                        MeasurementForm = modelform_factory(
                            model,
                            exclude=("base",)
                        )

                        measurement_instance = model.objects.filter(base=base).first()

                        print("MEASUREMENT INSTANCE:", measurement_instance)

                        measurement_prefix = f"measure-{form_prefix}"

                        print("MEASUREMENT PREFIX:", measurement_prefix)

                        # 🔎 Print all POST keys for debugging
                        print("---- POST KEYS ----")
                        for k in request.POST.keys():
                            if measurement_prefix in k:
                                print("POST FIELD:", k, "=", request.POST.get(k))
                        print("-------------------")

                        measurement_form = MeasurementForm(
                            request.POST,
                            instance=measurement_instance,
                            prefix=measurement_prefix
                        )

                        print("FORM IS VALID:", measurement_form.is_valid())

                        if measurement_form.is_valid():

                            measurement = measurement_form.save(commit=False)
                            measurement.base = base
                            measurement.save()

                            print("✅ MEASUREMENT SAVED:", measurement.id)

                        else:
                            print("❌ MEASUREMENT ERRORS:", measurement_form.errors)



                order.total_amount = total
                order.save()

            print("\n========== ORDER SAVED ==========\n")

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

            client_photo_formset = ClientPhotoFormSet(
                prefix="client_photos"
            )

    # ===============================
    # BUILD ITEM + PHOTO FORMSETS
    # ===============================

    item_forms_with_photos = []

    for form in item_formset.forms:

        item = form.instance

        # ------------------------------
        # PHOTO FORMSET
        # ------------------------------

        photo_formset = OrderItemPhotoFormSet(
            request.POST or None,
            request.FILES or None,
            instance=item,
            prefix=f"photos-{form.prefix}"
        )

        # ------------------------------
        # MEASUREMENT FORM
        # ------------------------------

        measurement_form = None

        if item.pk and item.product_type:

            model_name = item.product_type.measurement_model
            model = apps.get_model("orders", model_name)

            base = BaseMeasurement.objects.filter(order_item=item).first()

            measurement_instance = None
            if base:
                measurement_instance = model.objects.filter(base=base).first()

            MeasurementForm = modelform_factory(
                model,
                exclude=("base",)
            )

            measurement_form = MeasurementForm(
                request.POST or None,
                instance=measurement_instance,
                prefix=f"measure-{form.prefix}"
            )

        item_forms_with_photos.append(
            (form, photo_formset, measurement_form)
        )
        

    # ===============================
    # ORDER DETAIL
    # ===============================

    selected_order = None
    order_id = request.GET.get("order")

    if order_id and not show_add_form and not show_edit_form:
        selected_order = get_object_or_404(
            Order.objects.prefetch_related(
                "client_photos",
                "items__photos",
                "items__measurement",
            ),
            pk=order_id
        )

    # ===============================
    # CONTEXT
    # ===============================

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
    orders = Order.objects.all()

    # 🔎 FILTERING
    status = request.GET.get("status")
    if status:
        orders = orders.filter(status=status)

    # 🔄 SORTING
    sort = request.GET.get("sort", "-created_at")

    # Protect against invalid sort values (security best practice)
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

    # 📄 PAGINATION
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
        return orders_table(request)  # re-render table

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
        }
    )







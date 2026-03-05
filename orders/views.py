from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from orders.models import Order, OrderItem, ProductType, BaseMeasurement
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .forms import OrderForm, OrderItemFormSet, get_measurement_form, OrderItemPhotoFormSet
from django.apps import apps
from django.forms import modelform_factory



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

    # ===============================
    # POST (CREATE ORDER)
    # ===============================

    if request.method == "POST":

        print("\n========== POST RECEIVED ==========\n")

        order_form = OrderForm(request.POST)

        item_formset = OrderItemFormSet(
            request.POST,
            request.FILES
        )

        print("ORDER VALID:", order_form.is_valid())
        print("ORDER ERRORS:", order_form.errors)

        print("ITEM FORMSET VALID:", item_formset.is_valid())
        print("ITEM FORMSET ERRORS:", item_formset.errors)
        print("ITEM NON FORM ERRORS:", item_formset.non_form_errors())

        if order_form.is_valid() and item_formset.is_valid():

            # 1️⃣ Save order
            order = order_form.save(commit=False)
            order.total_amount = 0
            order.save()

            # 2️⃣ Rebind formset with instance
            item_formset = OrderItemFormSet(
                request.POST,
                request.FILES,
                instance=order
            )

            print("REBIND ITEM FORMSET VALID:", item_formset.is_valid())
            print("REBIND ITEM FORMSET ERRORS:", item_formset.errors)

            if not item_formset.is_valid():
                print("Rebind failed — stopping save.")
                show_add_form = True
            else:
                items = item_formset.save(commit=False)

            total = 0

            # ✅ FIX: enumerate to get index
            for index, item in enumerate(items):

                print(f"\n--- Saving Item Index {index} ---")

                item.order = order
                item.save()
                total += item.total_price

                form_prefix = item_formset.forms[index].prefix
                print("Item Form Prefix:", form_prefix)

                # ===============================
                # SAVE PHOTOS
                # ===============================

                photo_formset = OrderItemPhotoFormSet(
                    request.POST,
                    request.FILES,
                    instance=item,
                    prefix=f"photos-{form_prefix}"
                )

                print("Photo Prefix:", f"photos-{form_prefix}")
                print("PHOTO VALID:", photo_formset.is_valid())
                print("PHOTO ERRORS:", photo_formset.errors)

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
                model_name = product_type.measurement_model
                model = apps.get_model("orders", model_name)

                base = BaseMeasurement.objects.create(order_item=item)

                MeasurementForm = modelform_factory(
                    model,
                    exclude=("base",)
                )

                measurement_form = MeasurementForm(
                    request.POST,
                    prefix=f"measure-{form_prefix}"  # ✅ FIXED
                )

                print("Measurement Prefix:", f"measure-{form_prefix}")
                print("MEASUREMENT VALID:", measurement_form.is_valid())
                print("MEASUREMENT ERRORS:", measurement_form.errors)

                if measurement_form.is_valid():
                    measurement = measurement_form.save(commit=False)
                    measurement.base = base
                    measurement.save()

            order.total_amount = total
            order.save()

            print("\n========== ORDER SAVED ==========\n")

            return redirect("orders:dashboard")

        show_add_form = True

    else:
        order_form = OrderForm()
        item_formset = OrderItemFormSet()

    # ===============================
    # BUILD ITEM + PHOTO FORMSETS
    # ===============================

    item_forms_with_photos = []

    for form in item_formset.forms:

        photo_formset = OrderItemPhotoFormSet(
            request.POST or None,
            request.FILES or None,
            instance=form.instance,
            prefix=f"photos-{form.prefix}"  # ✅ MUST MATCH VIEW
        )

        item_forms_with_photos.append((form, photo_formset))

    # ===============================
    # ORDER DETAIL
    # ===============================

    selected_order = None
    order_id = request.GET.get("order")

    if order_id and not show_add_form:
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
        "order_form": order_form,
        "item_formset": item_formset,   # ✅ IMPORTANT (needed in template)
        "item_forms_with_photos": item_forms_with_photos,
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


@user_passes_test(staff_check)
def order_detail(request, pk):
    return HttpResponse(f"Order detail {pk}")

@user_passes_test(staff_check)
def order_edit(request, pk):
    return HttpResponse(f"Edit order {pk}")








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



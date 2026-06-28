"""
orders/views_staff.py
Staff management -- owner only, per tenant.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import get_user_model
from orders.models import StaffProfile

logger = logging.getLogger(__name__)
User = get_user_model()


def owner_check(request):
    try:
        role = request.user.staff_profile.role
        if role not in ("owner", "manager") and not request.user.is_superuser:
            return HttpResponse("Only owner or manager can manage staff.", status=403)
    except Exception:
        if not request.user.is_superuser:
            return HttpResponse("Only owner or manager can manage staff.", status=403)
    return None


@login_required
def staff_list(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    check = owner_check(request)
    if check:
        return check
    staff = User.objects.filter(
        tenant=tenant, is_staff=True, is_superuser=False
    ).select_related("staff_profile").order_by("first_name", "last_name", "username")
    return render(request, "orders/staff/staff_list.html", {"staff": staff})


@login_required
def staff_add(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    check = owner_check(request)
    if check:
        return check
    errors = {}
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        username   = request.POST.get("username", "").strip().lower()
        password   = request.POST.get("password", "")
        email      = request.POST.get("email", "").strip()
        role       = request.POST.get("role", "salesman")
        commission = request.POST.get("commission", "0").strip()
        can_delete = bool(request.POST.get("can_delete"))
        if not first_name:
            errors["first_name"] = "First name is required"
        if not username:
            errors["username"] = "Username is required"
        elif User.objects.filter(username=username).exists():
            errors["username"] = f"Username already taken"
        if not password or len(password) < 8:
            errors["password"] = "Password must be at least 8 characters"
        try:
            commission_val = float(commission)
            if commission_val < 0 or commission_val > 100:
                errors["commission"] = "Must be between 0 and 100"
        except ValueError:
            errors["commission"] = "Must be a number"
            commission_val = 0
        if not errors:
            user = User.objects.create_user(
                username=username, password=password, email=email,
                first_name=first_name, last_name=last_name,
                tenant=tenant, is_staff=True, is_tenant=True, can_delete=can_delete,
            )
            StaffProfile.objects.create(
                user=user, role=role,
                default_commission_percentage=commission_val,
            )
            messages.success(request, f"Staff member {first_name} {last_name} added!")
            return redirect("orders:staff_list")
    return render(request, "orders/staff/staff_form.html", {
        "is_edit": False, "errors": errors,
        "form_data": request.POST, "roles": StaffProfile.ROLE_CHOICES,
    })


@login_required
def staff_edit(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    check = owner_check(request)
    if check:
        return check
    user = get_object_or_404(User, pk=pk, tenant=tenant, is_superuser=False)
    try:
        profile = user.staff_profile
    except Exception:
        profile = StaffProfile.objects.create(user=user, role="salesman")
    errors = {}
    if request.method == "POST":
        first_name   = request.POST.get("first_name", "").strip()
        last_name    = request.POST.get("last_name", "").strip()
        email        = request.POST.get("email", "").strip()
        role         = request.POST.get("role", "salesman")
        commission   = request.POST.get("commission", "0").strip()
        can_delete   = bool(request.POST.get("can_delete"))
        new_password = request.POST.get("new_password", "").strip()
        if not first_name:
            errors["first_name"] = "First name is required"
        try:
            commission_val = float(commission)
        except ValueError:
            errors["commission"] = "Must be a number"
            commission_val = 0
        if new_password and len(new_password) < 8:
            errors["new_password"] = "New password must be at least 8 characters"
        if not errors:
            user.first_name = first_name
            user.last_name  = last_name
            user.email      = email
            user.can_delete = can_delete
            if new_password:
                user.set_password(new_password)
            user.save()
            profile.role = role
            profile.default_commission_percentage = commission_val
            profile.save()
            messages.success(request, f"Staff member {first_name} updated!")
            return redirect("orders:staff_list")
    return render(request, "orders/staff/staff_form.html", {
        "is_edit": True, "staff_user": user, "profile": profile,
        "errors": errors,
        "form_data": request.POST or {
            "first_name": user.first_name, "last_name": user.last_name,
            "email": user.email, "role": profile.role,
            "commission": profile.default_commission_percentage,
            "can_delete": user.can_delete,
        },
        "roles": StaffProfile.ROLE_CHOICES,
    })


@login_required
def staff_toggle(request, pk):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return HttpResponse("Tenant not found", status=404)
    check = owner_check(request)
    if check:
        return check
    if request.method != "POST":
        return HttpResponse(status=405)
    user = get_object_or_404(User, pk=pk, tenant=tenant, is_superuser=False)
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("orders:staff_list")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"{user.get_full_name() or user.username} {status}.")
    return redirect("orders:staff_list")

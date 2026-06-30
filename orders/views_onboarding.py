"""
orders/views_onboarding.py
Tenant onboarding flow — superuser only.
Creates a new tenant + owner user in one step.
"""
import logging
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction

from orders.models import Tenant
from accounts.models import CustomUser

logger = logging.getLogger(__name__)


def superuser_check(user):
    return user.is_authenticated and user.is_superuser


@user_passes_test(superuser_check, login_url='/accounts/login/')
def onboarding_view(request):
    """Step 1 — Create new tenant shop."""
    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = request.POST
        shop_name    = request.POST.get('shop_name', '').strip()
        subdomain    = request.POST.get('subdomain', '').strip().lower()
        owner_name   = request.POST.get('owner_name', '').strip()
        owner_email  = request.POST.get('owner_email', '').strip()
        owner_phone  = request.POST.get('owner_phone', '').strip()
        username     = request.POST.get('username', '').strip().lower()
        password     = request.POST.get('password', '')
        package              = request.POST.get('package', 'studio')
        whatsapp_token       = request.POST.get('whatsapp_token', '').strip()
        whatsapp_phone_id    = request.POST.get('whatsapp_phone_number_id', '').strip()
        has_catalogue        = bool(request.POST.get('has_catalogue'))
        catalogue_subdomain  = request.POST.get('catalogue_subdomain', '').strip().lower()
        display_key          = request.POST.get('display_key', '').strip().lower()
        custom_domain        = request.POST.get('custom_domain', '').strip().lower()
        shop_phone           = request.POST.get('shop_phone', '').strip()
        shop_street_address  = request.POST.get('shop_street_address', '').strip()
        shop_city            = request.POST.get('shop_city', '').strip()
        shop_state           = request.POST.get('shop_state', '').strip()
        shop_postcode        = request.POST.get('shop_postcode', '').strip()
        shop_country         = request.POST.get('shop_country', '').strip()

        # Validate
        if not shop_name:
            errors['shop_name'] = 'Shop name is required'
        if not subdomain:
            errors['subdomain'] = 'Subdomain is required'
        elif not subdomain.isalnum() and '-' not in subdomain:
            errors['subdomain'] = 'Subdomain must be letters, numbers or hyphens only'
        elif Tenant.objects.filter(subdomain=subdomain).exists():
            errors['subdomain'] = f'Subdomain "{subdomain}" is already taken'
        if not username:
            errors['username'] = 'Username is required'
        elif CustomUser.objects.filter(username=username).exists():
            errors['username'] = f'Username "{username}" is already taken'
        if not password or len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters'
        if not owner_name:
            errors['owner_name'] = 'Owner name is required'

        if not errors:
            try:
                with transaction.atomic():
                    # Create tenant
                    tenant = Tenant.objects.create(
                        name=shop_name,
                        subdomain=subdomain,
                        is_active=True,
                        package=package,
                        whatsapp_token=whatsapp_token,
                        whatsapp_phone_number_id=whatsapp_phone_id,
                        has_catalogue=has_catalogue,
                        catalogue_subdomain=catalogue_subdomain,
                        display_key=display_key,
                        custom_domain=custom_domain,
                        phone=shop_phone,
                        street_address=shop_street_address,
                        city=shop_city,
                        state=shop_state,
                        postcode=shop_postcode,
                        country=shop_country,
                    )
                    # Handle logo upload
                    if request.FILES.get('logo'):
                        tenant.logo = request.FILES['logo']
                        tenant.save(update_fields=['logo'])
                    # Handle favicon upload
                    if request.FILES.get('favicon'):
                        tenant.favicon = request.FILES['favicon']
                        tenant.save(update_fields=['favicon'])
                    # Create owner user
                    owner = CustomUser.objects.create_user(
                        username=username,
                        password=password,
                        email=owner_email,
                        first_name=owner_name,
                        tenant=tenant,
                        is_staff=True,
                        is_tenant=True,
                        can_delete=True,
                    )
                    logger.info(
                        f'New tenant created: {shop_name} ({subdomain}) '
                        f'by {request.user.username}'
                    )
                    return redirect('orders:onboarding_success', subdomain=subdomain)
            except Exception as e:
                logger.error(f'Tenant creation error: {e}')
                errors['non_field_error'] = f'Error creating tenant: {str(e)}'

    return render(request, 'orders/onboarding.html', {
        'errors':    errors,
        'form_data': form_data,
    })


@user_passes_test(superuser_check, login_url='/accounts/login/')
def onboarding_success_view(request, subdomain):
    """Step 2 — Success page with setup instructions."""
    tenant = Tenant.objects.filter(subdomain=subdomain).first()
    if tenant and tenant.custom_domain:
        studio_url = f'https://{tenant.custom_domain}'
    else:
        studio_url = f'https://{subdomain}.emporiumarmani.com'
    return render(request, 'orders/onboarding_success.html', {
        'tenant':     tenant,
        'subdomain':  subdomain,
        'studio_url': studio_url,
    })
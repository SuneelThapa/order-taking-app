# orders/middleware/tenant_middleware.py
from django.http import Http404
from django.conf import settings  # <-- needed for settings.DEBUG
from orders.models.tenant import Tenant

class TenantMiddleware:
    """
    Determine tenant from subdomain and attach it to request.
    Fallbacks to first tenant for local dev if DEBUG=True.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]  # remove port
        subdomain = host.split('.')[0]           # first part of host

        try:
            tenant = Tenant.objects.get(subdomain=subdomain)
        except Tenant.DoesNotExist:
            # Local development fallback
            if host in ["127.0.0.1", "localhost"] and settings.DEBUG:
                tenant = Tenant.objects.first()
            else:
                raise Http404("Tenant not found")

        request.tenant = tenant
        response = self.get_response(request)
        return response
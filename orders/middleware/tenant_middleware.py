from django.http import Http404
from django.conf import settings
from orders.models.tenant import Tenant


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        parts = host.split('.')
        subdomain = parts[0]
        tenant = None

        # 1. Check custom_domain first (e.g. studio.sukhumvittailors.com)
        try:
            tenant = Tenant.objects.get(custom_domain=host, is_active=True)
        except Tenant.DoesNotExist:
            pass

        # 2. Fall back to subdomain match
        if not tenant:
            try:
                tenant = Tenant.objects.get(subdomain=subdomain, is_active=True)
            except Tenant.DoesNotExist:
                # 3. Fallback: only known bare domains and local dev
                BARE_DOMAINS = {
                    "emporiumarmani.com",
                    "www.emporiumarmani.com",
                    "143.198.207.146",
                    "127.0.0.1",
                    "localhost",
                }
                if host in BARE_DOMAINS or settings.DEBUG:
                    tenant = Tenant.objects.first()
                else:
                    raise Http404("Tenant not found")

        if not tenant:
            raise Http404("No tenant configured")

        request.tenant = tenant
        response = self.get_response(request)
        return response
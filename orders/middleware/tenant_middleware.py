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

        try:
            tenant = Tenant.objects.get(subdomain=subdomain)
        except Tenant.DoesNotExist:
            # Fallback: localhost, IP address, or DEBUG mode
            if (host in ["127.0.0.1", "localhost"]
                    or host == "143.198.207.146"
                    or settings.DEBUG
                    or len(parts) < 3):
                tenant = Tenant.objects.first()
            else:
                raise Http404("Tenant not found")

        if not tenant:
            raise Http404("No tenant configured")

        request.tenant = tenant
        response = self.get_response(request)
        return response

from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from orders.models import Order

@login_required
@require_GET
def check_external_order_number(request):
    value      = request.GET.get('value', '').strip()
    exclude_pk = request.GET.get('exclude_pk', '')
    tenant     = request.tenant
    if not value:
        return HttpResponse('')
    qs = Order.objects.filter(tenant=tenant, external_order_number=value)
    if exclude_pk:
        try:
            qs = qs.exclude(pk=int(exclude_pk))
        except (ValueError, TypeError):
            pass
    if qs.exists():
        existing = qs.first()
        html = f'<div class="text-danger small mt-1"><i class="bi bi-x-circle me-1"></i>Already exists - order <strong>#{existing.order_number}</strong> ({existing.client.name})</div>'
    else:
        html = '<div class="text-success small mt-1"><i class="bi bi-check-circle me-1"></i>Available</div>'
    return HttpResponse(html)

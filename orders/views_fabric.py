"""
orders/views_fabric.py
Fabric library management — per tenant.
Only accessible when tenant.has_fabric_library is True.
"""
import json
import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.db.models import Q

from orders.models import Fabric, FabricCategory

logger = logging.getLogger(__name__)


def fabric_check(request):
    """Return 403 if tenant doesn't have fabric library enabled."""
    tenant = getattr(request, 'tenant', None)
    if not tenant or not tenant.has_fabric_library:
        return HttpResponse('Fabric library not enabled for this shop.', status=403)
    return None


@login_required
def fabric_list(request):
    """List all fabrics for this tenant, filterable by category."""
    check = fabric_check(request)
    if check:
        return check

    tenant   = request.tenant
    category = request.GET.get('category', '')
    q        = request.GET.get('q', '').strip()

    fabrics = Fabric.objects.filter(tenant=tenant, is_active=True).select_related('category')

    if category:
        fabrics = fabrics.filter(category__name=category)
    if q:
        fabrics = fabrics.filter(
            Q(sku_article__icontains=q) |
            Q(name__icontains=q) |
            Q(brand__icontains=q) |
            Q(colour__icontains=q) |
            Q(composition__icontains=q)
        )

    categories = FabricCategory.objects.filter(tenant=tenant)

    return render(request, 'orders/fabrics/fabric_list.html', {
        'fabrics':        fabrics,
        'categories':     categories,
        'selected_cat':   category,
        'q':              q,
    })


@login_required
def fabric_create(request):
    """Create a new fabric."""
    check = fabric_check(request)
    if check:
        return check

    tenant     = request.tenant
    categories = FabricCategory.objects.filter(tenant=tenant)
    errors     = {}

    if request.method == 'POST':
        sku_article     = request.POST.get('sku_article', '').strip()
        name            = request.POST.get('name', '').strip()
        category_id     = request.POST.get('category', '')
        brand           = request.POST.get('brand', '').strip()
        composition     = request.POST.get('composition', '').strip()
        weight          = request.POST.get('weight', '').strip()
        width           = request.POST.get('width', '').strip()
        pattern         = request.POST.get('pattern', '').strip()
        colour          = request.POST.get('colour', '').strip()
        collection      = request.POST.get('collection', '').strip()
        details         = request.POST.get('details', '').strip()
        price_per_metre = request.POST.get('price_per_metre', '').strip()

        # Validate
        if not sku_article:
            errors['sku_article'] = 'SKU / Article code is required'
        elif Fabric.objects.filter(tenant=tenant, sku_article=sku_article).exists():
            errors['sku_article'] = f'SKU "{sku_article}" already exists'
        if not name:
            errors['name'] = 'Fabric name is required'

        if not errors:
            category = None
            if category_id:
                try:
                    category = FabricCategory.objects.get(pk=category_id, tenant=tenant)
                except FabricCategory.DoesNotExist:
                    pass

            fabric = Fabric.objects.create(
                tenant          = tenant,
                category        = category,
                sku_article     = sku_article,
                name            = name,
                brand           = brand,
                composition     = composition,
                weight          = weight,
                width           = width,
                pattern         = pattern,
                colour          = colour,
                collection      = collection,
                details         = details,
                price_per_metre = price_per_metre or None,
            )
            # Handle image upload
            if request.FILES.get('image'):
                fabric.image = request.FILES['image']
                fabric.save(update_fields=['image'])

            messages.success(request, f'Fabric {sku_article} created!')
            return redirect('orders:fabric_list')

    return render(request, 'orders/fabrics/fabric_form.html', {
        'categories': categories,
        'errors':     errors,
        'form_data':  request.POST,
        'is_edit':    False,
    })


@login_required
def fabric_edit(request, pk):
    """Edit an existing fabric."""
    check = fabric_check(request)
    if check:
        return check

    tenant  = request.tenant
    fabric  = get_object_or_404(Fabric, pk=pk, tenant=tenant)
    categories = FabricCategory.objects.filter(tenant=tenant)
    errors  = {}

    if request.method == 'POST':
        sku_article     = request.POST.get('sku_article', '').strip()
        name            = request.POST.get('name', '').strip()
        category_id     = request.POST.get('category', '')
        brand           = request.POST.get('brand', '').strip()
        composition     = request.POST.get('composition', '').strip()
        weight          = request.POST.get('weight', '').strip()
        width           = request.POST.get('width', '').strip()
        pattern         = request.POST.get('pattern', '').strip()
        colour          = request.POST.get('colour', '').strip()
        collection      = request.POST.get('collection', '').strip()
        details         = request.POST.get('details', '').strip()
        price_per_metre = request.POST.get('price_per_metre', '').strip()

        if not sku_article:
            errors['sku_article'] = 'SKU / Article code is required'
        elif Fabric.objects.filter(tenant=tenant, sku_article=sku_article).exclude(pk=pk).exists():
            errors['sku_article'] = f'SKU "{sku_article}" already exists'
        if not name:
            errors['name'] = 'Fabric name is required'

        if not errors:
            category = None
            if category_id:
                try:
                    category = FabricCategory.objects.get(pk=category_id, tenant=tenant)
                except FabricCategory.DoesNotExist:
                    pass

            fabric.sku_article     = sku_article
            fabric.name            = name
            fabric.category        = category
            fabric.brand           = brand
            fabric.composition     = composition
            fabric.weight          = weight
            fabric.width           = width
            fabric.pattern         = pattern
            fabric.colour          = colour
            fabric.collection      = collection
            fabric.details         = details
            fabric.price_per_metre = price_per_metre or None
            fabric.save()

            if request.FILES.get('image'):
                fabric.image = request.FILES['image']
                fabric.save(update_fields=['image'])

            messages.success(request, f'Fabric {sku_article} updated!')
            return redirect('orders:fabric_list')

    return render(request, 'orders/fabrics/fabric_form.html', {
        'categories': categories,
        'errors':     errors,
        'fabric':     fabric,
        'form_data':  request.POST or {
            'sku_article':     fabric.sku_article,
            'name':            fabric.name,
            'category':        fabric.category_id or '',
            'brand':           fabric.brand,
            'composition':     fabric.composition,
            'weight':          fabric.weight,
            'width':           fabric.width,
            'pattern':         fabric.pattern,
            'colour':          fabric.colour,
            'collection':      fabric.collection,
            'details':         fabric.details,
            'price_per_metre': fabric.price_per_metre or '',
        },
        'is_edit': True,
    })


@login_required
@require_POST
def fabric_delete(request, pk):
    """Soft delete — mark as inactive."""
    check = fabric_check(request)
    if check:
        return check

    fabric = get_object_or_404(Fabric, pk=pk, tenant=request.tenant)
    fabric.is_active = False
    fabric.save(update_fields=['is_active'])
    messages.success(request, f'Fabric {fabric.sku_article} removed.')
    return redirect('orders:fabric_list')


@login_required
@require_GET
def fabric_search(request):
    """
    HTMX search endpoint for order form fabric picker.
    Returns small HTML list of matching fabrics.
    """
    tenant   = request.tenant
    q        = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')

    if not q and not category:
        return HttpResponse('')

    fabrics = Fabric.objects.filter(
        tenant=tenant, is_active=True
    ).select_related('category')

    if category:
        fabrics = fabrics.filter(category__name=category)
    if q:
        fabrics = fabrics.filter(
            Q(sku_article__icontains=q) |
            Q(name__icontains=q) |
            Q(colour__icontains=q) |
            Q(composition__icontains=q)
        )

    fabrics = fabrics[:20]

    # Return JSON for Alpine.js picker
    if request.headers.get('Accept') == 'application/json' or request.GET.get('fmt') == 'json':
        import json
        data = []
        for f in fabrics:
            data.append({
                'pk':          f.pk,
                'code':        f.sku_article,
                'name':        f.name,
                'composition': f.composition,
                'image':       f.image.url if f.image else '',
                'price':       str(f.price_per_metre) if f.price_per_metre else '',
            })
        from django.http import JsonResponse
        return JsonResponse(data, safe=False)

    return render(request, 'orders/fabrics/_fabric_search_results.html', {
        'fabrics': fabrics,
    })
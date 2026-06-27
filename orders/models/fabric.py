from django.db import models
from cloudinary.models import CloudinaryField
from .tenant import Tenant


class FabricCategory(models.Model):
    CATEGORY_CHOICES = [
        ('suiting',    'Suiting'),
        ('shirting',   'Shirting'),
        ('sport_coats', 'Sport Coats'),
        ('overcoats',   'Overcoats'),
        ('trousering', 'Trousering'),
        ('lining',     'Lining'),
        ('other',      'Other'),
    ]
    name   = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='fabric_categories'
    )

    class Meta:
        verbose_name = 'Fabric Category'
        verbose_name_plural = 'Fabric Categories'
        unique_together = [('tenant', 'name')]
        ordering = ['name']

    def __str__(self):
        return self.get_name_display()


class Fabric(models.Model):
    tenant      = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='fabrics'
    )
    category    = models.ForeignKey(
        FabricCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fabrics'
    )
    sku_article = models.CharField(max_length=50, db_index=True, help_text='SKU / Article code e.g. GT5258')
    name        = models.CharField(max_length=255, help_text='Fabric name e.g. Gray Plain')
    brand       = models.CharField(max_length=100, blank=True, default='')
    composition = models.CharField(max_length=200, blank=True, default='', help_text='e.g. 100% Wool (Super 150S)')
    weight      = models.CharField(max_length=50, blank=True, default='', help_text='e.g. 280 g.')
    width       = models.CharField(max_length=50, blank=True, default='', help_text='e.g. 60 in or 136 cm.')
    pattern     = models.CharField(max_length=100, blank=True, default='', help_text='e.g. Plain, Stripe, Check, Print')
    colour      = models.CharField(max_length=200, blank=True, default='')
    collection  = models.CharField(max_length=100, blank=True, default='')
    details     = models.TextField(blank=True, default='')
    price_per_metre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image       = CloudinaryField('fabric_image', blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Fabric'
        verbose_name_plural = 'Fabrics'
        ordering = ['category', 'name']
        unique_together = [('tenant', 'sku_article')]

    def __str__(self):
        return f'{self.sku_article} - {self.name}'

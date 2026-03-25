from django.db import models
from django.utils import timezone


class Order(models.Model):

    STATUS_CHOICES = [
        ('new', 'new'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('ready', 'Ready'),
        ('delivered', 'Delivered'),
    ]

    CONTACT_METHODS = [
        ('whatsapp', 'WhatsApp'),
        ('viber', 'Viber'),
    ]

    order_number = models.CharField(max_length=20, unique=True, db_index=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE, related_name='orders')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, null=True)
    postcode = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    contact_method = models.CharField(
        max_length=20,
        choices=CONTACT_METHODS,
        default='whatsapp'
    )

    phone = models.CharField(max_length=50)
    email = models.EmailField()

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    note = models.TextField(blank=True, null=True)

    ready_date = models.DateField(blank=True, null=True)

    is_urgent = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        db_index=True
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):

        if not self.order_number:

            year_prefix = timezone.now().strftime("%y")

            last_order = (
                Order.objects
                .filter(order_number__startswith=year_prefix)
                .order_by("-order_number")
                .first()
            )

            if last_order:
                last_number = int(last_order.order_number[2:])
                new_number = last_number + 1
            else:
                new_number = 1

            self.order_number = f"{year_prefix}{new_number:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number
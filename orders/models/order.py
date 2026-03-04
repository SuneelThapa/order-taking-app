from django.db import models


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

    order_number = models.CharField(max_length=20, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    # ------------------------------
    # SHIPPING ADDRESS
    # ------------------------------
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

    # ✅ NEW FIELDS
    note = models.TextField(blank=True, null=True)

    ready_date = models.DateField(blank=True, null=True)

    is_urgent = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    def __str__(self):
        return self.order_number
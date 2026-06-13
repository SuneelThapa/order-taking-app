from django.db import models
from django.conf import settings


class StaffProfile(models.Model):

    ROLE_CHOICES = [
        ('owner',   'Owner'),
        ('manager', 'Manager'),
        ('staff',   'Staff'),
    ]

    EMPLOYMENT_TYPES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('commission_only', 'Commission Only'),
    ]

    SALARY_PERIODS = [
        ('monthly', 'Monthly'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )

    # Compensation — salary always in THB
    base_salary = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0,
        help_text="Monthly base salary in THB"
    )
    salary_period = models.CharField(
        max_length=20,
        choices=SALARY_PERIODS,
        default='monthly'
    )
    default_commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0,
        help_text="Default commission % copied to OrderStaff when added to an order. Admin can override per order."
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPES,
        default='full_time'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='staff',
        help_text="Owner and Manager can modify staff assignments and approve refunds."
    )
    join_date = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — Staff Profile"
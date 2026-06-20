from django.db import models


class BodyMeasurement(models.Model):
    """
    Full body measurements taken once per order item.
    Gender-aware: men/ladies fields shown based on gender selection.
    """
    GENDER_CHOICES = [
        ('men',    'Men'),
        ('ladies', 'Ladies'),
    ]
    SHOULDER_POSTURE_CHOICES = [
        ('normal', 'Normal'),
        ('slope',  'Slope'),
        ('square', 'Square'),
    ]
    STOMACH_DESC_CHOICES = [
        ('normal', 'Normal'),
        ('medium', 'Medium'),
        ('large',  'Large'),
    ]
    CHEST_DESC_CHOICES = [
        ('thin',     'Thin'),
        ('fit',      'Fit'),
        ('normal',   'Normal'),
        ('muscular', 'Muscular'),
        ('large',    'Large'),
    ]

    order_item = models.OneToOneField(
        'orders.OrderItem',
        on_delete=models.CASCADE,
        related_name='body_measurement'
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default='men',
    )

    # ── Universal body measurements (Men & Ladies) ───────
    neck     = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Neck')
    shoulder = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Shoulder')
    sleeve   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Sleeve')
    biceps   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Biceps')
    chest    = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Chest')
    stomach  = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Stomach')
    hips     = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Hip')
    height   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Height')
    weight   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Weight')

    # ── Men — Upper body ─────────────────────────────────
    length   = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Length')
    front    = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Front')
    back     = models.DecimalField(max_digits=6, decimal_places=1,
                                   null=True, blank=True, verbose_name='Back')

    # ── Men — Lower body ─────────────────────────────────
    pants_waist  = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Pants Waist')
    pants_hip    = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Pants Hip')
    belly        = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Belly')
    crotch       = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Crotch')
    thigh        = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Thigh')
    knee         = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Knee')
    cuff         = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Cuff')
    pants_length = models.DecimalField(max_digits=6, decimal_places=1,
                                       null=True, blank=True, verbose_name='Pants Length')

    # ── Men — Posture & Description ───────────────────────
    shoulder_posture = models.CharField(
        max_length=10,
        choices=SHOULDER_POSTURE_CHOICES,
        null=True, blank=True,
        verbose_name='Shoulder Posture'
    )
    stomach_description = models.CharField(
        max_length=10,
        choices=STOMACH_DESC_CHOICES,
        null=True, blank=True,
        verbose_name='Stomach'
    )
    chest_description = models.CharField(
        max_length=10,
        choices=CHEST_DESC_CHOICES,
        null=True, blank=True,
        verbose_name='Chest Type'
    )

    # ── Ladies-specific ───────────────────────────────────
    high_chest = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='High Chest')
    upper_hips = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Upper Hips')
    deep_front = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Deep Front')
    deep_back = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Deep Back')
    shoulder_to_middle_breast = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Shoulder to Middle Breast')
    shoulder_to_under_breast = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Shoulder to Under Breast')
    middle_breast_to_middle_breast = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Middle Breast to Middle Breast')
    shoulder_to_back = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Shoulder to Back')
    shoulder_to_waist = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        verbose_name='Shoulder to Waist')

    class Meta:
        verbose_name        = 'Body Measurement'
        verbose_name_plural = 'Body Measurements'

    def __str__(self):
        return f'{self.get_gender_display()} — {self.order_item}'

    # ── Field groups for template rendering ───────────────
    MEN_UPPER_FIELDS = [
        'neck', 'shoulder', 'sleeve', 'biceps',
        'chest', 'stomach', 'hips', 'length', 'front', 'back',
    ]
    MEN_LOWER_FIELDS = [
        'pants_waist', 'pants_hip', 'belly', 'crotch',
        'thigh', 'knee', 'cuff', 'pants_length',
    ]
    MEN_GENERAL_FIELDS = ['height', 'weight']
    MEN_DESC_FIELDS = ['shoulder_posture', 'stomach_description', 'chest_description']
    LADIES_EXTRA_FIELDS = [
        'high_chest', 'upper_hips', 'deep_front', 'deep_back',
        'shoulder_to_middle_breast', 'shoulder_to_under_breast',
        'middle_breast_to_middle_breast',
        'shoulder_to_back', 'shoulder_to_waist',
    ]
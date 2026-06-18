# orders/forms.py
from django import forms
from django.forms import inlineformset_factory, formset_factory, modelform_factory
from django.urls import reverse_lazy
from django.apps import apps
from functools import lru_cache

from .models import (
    Order, Client, OrderItem, OrderItemPhoto,
    ClientPhoto, Payment, Delivery, OrderStaff,
)
from .models.order import CURRENCY_CHOICES


# =====================================================
# BASE STYLED FORM
# =====================================================
class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                continue
            existing = field.widget.attrs.get("class", "")
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = f"{existing} form-select".strip()
            else:
                field.widget.attrs["class"] = f"{existing} form-control".strip()


# =====================================================
# CLIENT FORM
# =====================================================
class ClientForm(StyledModelForm):
    class Meta:
        model = Client
        fields = [
            "name", "phone", "email", "contact_method",
            "acquisition_channel", "referral_source", "referred_by",
            "street_address", "city", "state", "postcode", "country",
            "notes", "marketing_consent",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}
        help_texts = {"phone": "E.164 format, e.g. +66812345678"}


# =====================================================
# ORDER FORM
# =====================================================
class OrderForm(StyledModelForm):
    status_hidden = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean_status(self):
        if self.cleaned_data.get("status_hidden"):
            return self.cleaned_data["status_hidden"]
        return self.cleaned_data.get("status")

    def __init__(self, *args, **kwargs):
        user   = kwargs.pop("user",   None)
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Make total_amount optional — view calculates it from items if blank
        self.fields["total_amount"].required = False
        self.fields["total_amount"].initial  = 0

        default = self._meta.model._meta.get_field("status").get_default()  # type: ignore
        current = self.instance.status if self.instance and self.instance.pk else default

        if "status" in self.fields:
            # 'canceled' is only reachable via the Cancel order button — never via edit form
            self.fields["status"].choices = [
                (v, l) for v, l in self.fields["status"].choices if v != "canceled"
            ]
            if user and getattr(user, "is_tenant", False):
                self.fields["status"].widget = forms.TextInput(attrs={
                    "class": "form-control",
                    "readonly": True,
                    "value": current.capitalize(),
                })
                self.fields["status_hidden"].initial = current

    class Meta:
        model = Order
        fields = [
            "parent_order", "status",  # 'client' handled via hidden input in template
            "hotel_name", "room_number", "departure_date",
            "street_address", "city", "state", "postcode", "country",
            "fitting_date", "fitting_time", "ready_date", "ready_time", "delivery_date", "delivery_time",
            "total_amount", "total_currency",
            "note", "internal_notes", "is_urgent",
        ]
        widgets = {
            "departure_date": forms.DateInput(attrs={"type": "date"}),
            "fitting_date":   forms.DateInput(attrs={"type": "date"}),
            "fitting_time":   forms.TimeInput(attrs={"type": "time"}),
            "ready_date":     forms.DateInput(attrs={"type": "date"}),
            "ready_time":     forms.TimeInput(attrs={"type": "time"}),
            "delivery_date":  forms.DateInput(attrs={"type": "date"}),
            "delivery_time":  forms.TimeInput(attrs={"type": "time"}),
            "note":           forms.Textarea(attrs={"rows": 3}),
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "hotel_name":      "Hotel name",
            "room_number":     "Room number",
            "departure_date":  "Departure date",
            "total_amount":    "Total amount",
            "total_currency":  "Currency",
            "note":            "Customer notes (shown on invoice)",
            "internal_notes":  "Internal notes (staff only)",
        }


# =====================================================
# DELIVERY FORM
# =====================================================
class DeliveryForm(StyledModelForm):
    class Meta:
        model = Delivery
        fields = [
            "type", "hotel_name", "room_number",
            "shipping_street", "shipping_city", "shipping_state",
            "shipping_postcode", "shipping_country", "delivery_notes",
        ]
        widgets = {"delivery_notes": forms.Textarea(attrs={"rows": 3})}


# =====================================================
# PAYMENT FORM
# =====================================================
class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        fields = [
            "original_amount", "currency",
            "exchange_rate_to_thb", "method", "type", "notes", "proof_image",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}
        help_texts = {
            "exchange_rate_to_thb": "THB=1 · Crypto=agreed fixed rate · Others=today's rate",
            "original_amount":      "Negative = refund (always THB, rate=1)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Amount optional — leave blank to skip saving the payment
        self.fields["original_amount"].required = False
        # Rate optional — defaults to 1 (THB stays 1, staff enters for foreign currency)
        self.fields["exchange_rate_to_thb"].required = False
        # Set initials to match select default options so that an untouched
        # extra form has has_changed()=False → empty_permitted kicks in → no validation
        self.fields["currency"].initial             = "THB"
        self.fields["method"].initial               = "cash"
        self.fields["type"].initial                 = "deposit"
        self.fields["exchange_rate_to_thb"].initial = 1
        self.fields["proof_image"].required = False
        self.fields["proof_image"].label    = "Proof image (optional)"

    def clean(self):
        cleaned  = super().clean()
        ptype    = cleaned.get("type")
        amount   = cleaned.get("original_amount")
        currency = cleaned.get("currency")
        if ptype == "refund":
            if amount is not None and amount >= 0:
                self.add_error("original_amount",
                               "Refund amount must be negative (e.g. -200).")
            if currency and currency != "THB":
                self.add_error("currency",
                               "Refunds must always be in THB.")
        return cleaned


# Non-inline formset — saved manually after the order is created
PaymentCreateFormSet = formset_factory(PaymentForm, extra=1, can_delete=True)


# =====================================================
# ORDER ITEM FORM
# =====================================================
class OrderItemForm(StyledModelForm):
    class Meta:
        model = OrderItem
        exclude = ("order",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price"].required = False
        self.fields["group_label"].required = False
        if self.prefix:
            self.fields["product_type"].widget.attrs.update({
                "hx-get":     reverse_lazy("orders:load_measurement_form"),
                "hx-trigger": "change",
                "hx-target":  f"#measurement-container-{self.prefix}",
                "hx-include": "this",
                "hx-vals":    f'{{"prefix": "{self.prefix}"}}',
            })


OrderItemFormSet = inlineformset_factory(
    Order, OrderItem, form=OrderItemForm, extra=1, can_delete=True
)


# =====================================================
# ORDER ITEM PHOTO FORM
# =====================================================
class OrderItemPhotoForm(forms.ModelForm):
    class Meta:
        model = OrderItemPhoto
        fields = ("image",)
        widgets = {
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control", "accept": "image/*"
            })
        }


OrderItemPhotoFormSet = inlineformset_factory(
    OrderItem, OrderItemPhoto, form=OrderItemPhotoForm, extra=0, can_delete=True
)


# =====================================================
# CLIENT PHOTO FORM
# =====================================================
class ClientPhotoForm(StyledModelForm):
    photo_type = forms.ChoiceField(choices=ClientPhoto.PHOTO_TYPES, required=False)
    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = ClientPhoto
        fields = ["photo_type", "image"]


ClientPhotoFormSet = inlineformset_factory(
    Order, ClientPhoto, form=ClientPhotoForm, extra=3, max_num=3, can_delete=False
)


# =====================================================
# ORDER STAFF FORM  (commission managed in admin only)
# =====================================================
class OrderStaffForm(StyledModelForm):
    class Meta:
        model = OrderStaff
        fields = ["user", "role"]
        labels = {"user": "Staff member"}


OrderStaffFormSet = inlineformset_factory(
    Order, OrderStaff, form=OrderStaffForm, extra=1, can_delete=True
)


# =====================================================
# MEASUREMENT FORM FACTORIES (cached)
# =====================================================
@lru_cache(maxsize=32)
def get_measurement_model(model_name):
    try:
        return apps.get_model("orders", model_name)
    except LookupError:
        return None


@lru_cache(maxsize=32)
def get_measurement_modelform(model):
    BaseForm = modelform_factory(model, exclude=("base",))

    class StyledMeasurementForm(BaseForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for field in self.fields.values():
                field.widget.attrs["class"] = "form-control"

    return StyledMeasurementForm


def get_measurement_form(product_type):
    model = get_measurement_model(product_type.measurement_model)
    if not model:
        return None
    return get_measurement_modelform(model)


# =====================================================
# CANCELLATION FORM
# =====================================================
from .models import CancellationRecord

class CancellationForm(StyledModelForm):

    class Meta:
        model  = CancellationRecord
        fields = ["cancellation_type", "cancel_reason", "resolution", "resolution_notes"]
        widgets = {
            "cancel_reason":    forms.Textarea(attrs={"rows": 3,
                "placeholder": "Describe the reason for cancellation…"}),
            "resolution_notes": forms.Textarea(attrs={"rows": 2,
                "placeholder": "Optional notes on the resolution…"}),
        }
        labels = {
            "cancellation_type": "Cancellation type",
            "cancel_reason":     "Reason",
            "resolution":        "Resolution",
            "resolution_notes":  "Resolution notes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resolution_notes"].required = False


# =====================================================
# CLIENT EDIT FORM
# =====================================================
class ClientEditForm(StyledModelForm):
    class Meta:
        model  = Client
        fields = [
            "name", "phone", "email", "contact_method",
            "acquisition_channel", "referral_source", "referred_by",
            "street_address", "city", "state", "postcode", "country",
            "notes", "marketing_consent", "is_active",
        ]
        labels = {
            "contact_method":    "Preferred contact",
            "acquisition_channel": "How they found us",
            "referral_source":   "Referral source",
            "referred_by":       "Referred by client",
            "marketing_consent": "Marketing consent (PDPA)",
            "is_active":         "Active client",
        }
        widgets = {
            "notes": forms.Textarea(attrs={
                "rows": 2,
                "placeholder": "Fabric preferences, fit notes, reminders…",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required          = False
        self.fields["referral_source"].required = False
        self.fields["referred_by"].required     = False
        self.fields["notes"].required           = False
        # referred_by: exclude self from choices
        if self.instance and self.instance.pk:
            self.fields["referred_by"].queryset = \
                Client.objects.exclude(pk=self.instance.pk)


# ─────────────────────────────────────────────────────────
# Body Measurement Form
# ─────────────────────────────────────────────────────────
from .models import BodyMeasurement

BODY_FIELDS_MEN_UPPER = [
    'neck', 'shoulder', 'sleeve', 'biceps',
    'chest', 'stomach', 'hips', 'length', 'front', 'back',
]

BODY_FIELDS_MEN_LOWER = [
    'pants_waist', 'pants_hip', 'belly', 'crotch',
    'thigh', 'knee', 'cuff', 'pants_length',
]

BODY_FIELDS_MEN_GENERAL = ['height', 'weight']

BODY_FIELDS_MEN = BODY_FIELDS_MEN_UPPER + BODY_FIELDS_MEN_LOWER + BODY_FIELDS_MEN_GENERAL

BODY_FIELDS_LADIES_EXTRA = [
    'high_chest', 'upper_hips',
    'deep_front', 'deep_back',
    'shoulder_to_middle_breast',
    'shoulder_to_under_breast',
    'middle_breast_to_middle_breast',
]

_decimal_widget = lambda: forms.NumberInput(attrs={
    'class': 'form-control form-control-sm',
    'step': '0.1',
})


class BodyMeasurementForm(forms.ModelForm):
    class Meta:
        model  = BodyMeasurement
        fields = (
            ['gender'] +
            BODY_FIELDS_MEN +
            ['shoulder_posture', 'stomach_description', 'chest_description'] +
            BODY_FIELDS_LADIES_EXTRA
        )
        widgets = {
            'gender': forms.RadioSelect(
                attrs={'class': 'form-check-input'}
            ),
            'shoulder_posture': forms.Select(
                attrs={'class': 'form-select form-select-sm'}
            ),
            'stomach_description': forms.Select(
                attrs={'class': 'form-select form-select-sm'}
            ),
            'chest_description': forms.Select(
                attrs={'class': 'form-select form-select-sm'}
            ),
            **{
                f: forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm',
                    'step': '0.1',
                })
                for f in BODY_FIELDS_MEN + BODY_FIELDS_LADIES_EXTRA
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields optional — body measurements are never required
        for field in self.fields.values():
            field.required = False
        # Default gender to 'men' if not provided
        self.fields['gender'].initial = 'men'
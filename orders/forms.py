# orders/forms.py
from django import forms
from django.forms import inlineformset_factory, modelform_factory
from django.urls import reverse
from django.apps import apps
from functools import lru_cache

from .models import Order, OrderItem, OrderItemPhoto, ClientPhoto


def validate_image_format(image):
    valid_types = ['image/jpeg', 'image/png']
    content_type = getattr(image, "content_type", None)
    if content_type not in valid_types:
        raise forms.ValidationError("Only JPG and PNG images are allowed.")
    return image


# =====================================================
# BASE STYLED FORM
# =====================================================
class StyledModelForm(forms.ModelForm):
    """Apply Bootstrap form-control to all fields except checkboxes and hidden fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                continue
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_class} form-control".strip()


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
        user = kwargs.pop("user", None)
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        model_default_status = self._meta.model._meta.get_field('status').get_default()  # type: ignore
        current_status = self.instance.status if self.instance and self.instance.pk else model_default_status

        if "status" in self.fields:
            if user and getattr(user, "is_tenant", False):
                self.fields["status"].widget = forms.TextInput(attrs={
                    "class": "form-control",
                    "readonly": True,
                    "value": current_status.capitalize(),
                })
                self.fields["status_hidden"].initial = current_status

    class Meta:
        model = Order
        fields = [
            "first_name", "last_name", "email", "phone", "contact_method",
            "street_address", "city", "state", "postcode", "country",
            "note", "ready_date", "is_urgent", "status",
        ]
        labels = {
            "first_name": "First name", "last_name": "Last name", "email": "Email address",
            "phone": "Phone number", "contact_method": "Preferred contact method",
            "street_address": "Street address", "city": "City", "state": "State / province",
            "postcode": "Postal code", "country": "Country", "note": "Notes",
            "ready_date": "Ready date", "is_urgent": "Urgent order", "status": "Order status",
        }
        widgets = {
            "ready_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


# =====================================================
# ORDER ITEM FORM
# =====================================================
class OrderItemForm(StyledModelForm):
    class Meta:
        model = OrderItem
        exclude = ("order",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # When the product type changes, htmx loads that type's measurement fields
        # into this row's measurement container. prefix is set by the formset (items-N).
        self.fields["product_type"].widget.attrs.update({
            "hx-get": reverse("orders:load_measurement_form"),
            "hx-trigger": "change",
            "hx-target": f"#measurement-container-{self.prefix}",
            "hx-include": "this",  # sends this select's value under its own name
            "hx-vals": '{"prefix": "%s"}' % self.prefix,
        })

    def clean(self):
        return super().clean()


OrderItemFormSet = inlineformset_factory(
    Order, OrderItem, form=OrderItemForm, extra=1, can_delete=True
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
# CLIENT PHOTO FORM (fixed 3 slots: front / side / back)
# =====================================================
class ClientPhotoForm(StyledModelForm):
    photo_type = forms.ChoiceField(choices=ClientPhoto.PHOTO_TYPES, required=False, label="Photo type")
    image = forms.ImageField(
        required=False, label="Upload photo",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = ClientPhoto
        fields = ["photo_type", "image"]


ClientPhotoFormSet = inlineformset_factory(
    Order, ClientPhoto, form=ClientPhotoForm, extra=3, max_num=3, can_delete=False
)
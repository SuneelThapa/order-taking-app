from django import forms
from django.forms import inlineformset_factory, modelform_factory
from django.apps import apps
from functools import lru_cache

from .models import Order, OrderItem, OrderItemPhoto, ClientPhoto


# =====================================================
# BASE STYLED FORM (Avoid repeating widget styling)
# =====================================================

class StyledModelForm(forms.ModelForm):
    """
    Automatically apply Bootstrap form-control class
    to all fields except checkboxes and hidden fields.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():

            # Skip checkboxes and hidden fields
            if isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                continue

            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_class} form-control".strip()


# =====================================================
# ORDER FORM
# =====================================================

class OrderForm(StyledModelForm):

    class Meta:
        model = Order
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "contact_method",
            "street_address",
            "city",
            "state",
            "postcode",
            "country",
            "note",
            "ready_date",
            "is_urgent",
            "status",
        ]

        labels = {
            "order_number": "Order Number",
            "first_name": "First Name",
            "last_name": "Last Name",
            "email": "Email Address",
            "phone": "Phone Number",
            "contact_method": "Preferred Contact Method",
            "street_address": "Street Address",
            "city": "City",
            "state": "State / Province",
            "postcode": "Postal Code",
            "country": "Country",
            "note": "Notes",
            "ready_date": "Ready Date",
            "is_urgent": "Urgent Order",
            "status": "Order Status",
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


OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True
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
                "class": "form-control",
                "accept": "image/*",
                "capture": "environment"
            })
        }


OrderItemPhotoFormSet = inlineformset_factory(
    OrderItem,
    OrderItemPhoto,
    form=OrderItemPhotoForm,
    extra=0,
    can_delete=True
)


# =====================================================
# MEASUREMENT MODEL CACHE
# =====================================================

@lru_cache(maxsize=32)
def get_measurement_model(model_name):
    """
    Cache measurement model lookup to avoid repeated
    apps.get_model calls (expensive).
    """

    try:
        return apps.get_model("orders", model_name)
    except LookupError:
        return None


# =====================================================
# MEASUREMENT FORM FACTORY CACHE
# =====================================================

@lru_cache(maxsize=32)
def get_measurement_modelform(model):
    """
    Cache modelform creation because modelform_factory
    is expensive.
    """

    BaseForm = modelform_factory(
        model,
        exclude=("base",)
    )

    class StyledMeasurementForm(BaseForm):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            for field in self.fields.values():
                field.widget.attrs["class"] = "form-control"

    return StyledMeasurementForm


# =====================================================
# MAIN DYNAMIC FORM LOADER
# =====================================================

def get_measurement_form(product_type):

    model_name = product_type.measurement_model

    model = get_measurement_model(model_name)

    if not model:
        return None

    return get_measurement_modelform(model)


# =====================================================
# CLIENT PHOTO FORM
# =====================================================

class ClientPhotoForm(StyledModelForm):

    photo_type = forms.ChoiceField(
        choices=ClientPhoto.PHOTO_TYPES,
        required=False,
        label="Photo Type"
    )

    image = forms.ImageField(
        required=False,
        label="Upload Photo",
        widget=forms.ClearableFileInput(attrs={
            "accept": "image/*",
            "capture": "environment"
        })
    )

    class Meta:
        model = ClientPhoto
        fields = ["photo_type", "image"]


ClientPhotoFormSet = inlineformset_factory(
    Order,
    ClientPhoto,
    form=ClientPhotoForm,
    extra=3,
    max_num=3,
    can_delete=False
)
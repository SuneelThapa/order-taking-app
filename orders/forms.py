# orders/forms.py
from django import forms
from django.forms import inlineformset_factory, modelform_factory
from django.apps import apps
from functools import lru_cache

from .models import Order, OrderItem, OrderItemPhoto, ClientPhoto


def validate_image_format(image):
    valid_types = ['image/jpeg', 'image/png']

    # Some files may not have content_type (rare but safe check)
    content_type = getattr(image, "content_type", None)

    if content_type not in valid_types:
        raise forms.ValidationError("Only JPG and PNG images are allowed.")

    return image

# =====================================================
# BASE STYLED FORM
# =====================================================
class StyledModelForm(forms.ModelForm):
    """
    Automatically apply Bootstrap form-control class
    to all fields except checkboxes and hidden fields.
    """

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
        # Use the hidden field if the status dropdown is disabled
        if self.cleaned_data.get("status_hidden"):
            return self.cleaned_data["status_hidden"]
        return self.cleaned_data.get("status")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)       # pass request.user
        tenant = kwargs.pop("tenant", None)   # pass tenant if needed
        super().__init__(*args, **kwargs)

        # Get model default for status
        model_default_status = self._meta.model._meta.get_field('status').get_default()  # type: ignore
        current_status = self.instance.status if self.instance and self.instance.pk else model_default_status

        if "status" in self.fields:
            if user and getattr(user, "is_tenant", False):
                # Tenant (staff or normal): read-only textbox + hidden field
                self.fields["status"].widget = forms.TextInput(attrs={
                    "class": "form-control",
                    "readonly": True,
                    "value": current_status.capitalize(),
                })
                self.fields["status_hidden"].initial = current_status
            else:
                # Admins: leave full dropdown (default widget)
                pass

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

    def clean(self):
        cleaned_data = super().clean()
        product_type = cleaned_data.get("product_type")
        product_name = cleaned_data.get("product_name")
        price = cleaned_data.get("price")

        if not product_type and not product_name and not price:
            return cleaned_data

        return cleaned_data

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
                "accept": "image/*"
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
    try:
        return apps.get_model("orders", model_name)
    except LookupError:
        return None

# =====================================================
# MEASUREMENT FORM FACTORY CACHE
# =====================================================
@lru_cache(maxsize=32)
def get_measurement_modelform(model):
    BaseForm = modelform_factory(model, exclude=("base",))
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
            "accept": "image/*"
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
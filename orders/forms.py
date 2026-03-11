from django import forms
from .models import Order, OrderItem, OrderItemPhoto, ClientPhoto
from django.forms import inlineformset_factory

from django.apps import apps
from django.forms import modelform_factory

from django.forms import modelformset_factory





class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            #"order_number",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

        # Remove form-control from checkbox
        self.fields["is_urgent"].widget.attrs.update({
            "class": ""
        })




class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        exclude = ("order",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})



OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    #fields=("image",),
    extra=1,
    can_delete=True
)




class OrderItemPhotoForm(forms.ModelForm):
    class Meta:
        model = OrderItemPhoto
        fields = ("image",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].widget.attrs.update({
            "class": "form-control",
            "accept": "image/*",          # only images
            
        })


OrderItemPhotoFormSet = inlineformset_factory(
    OrderItem,
    OrderItemPhoto,
    form=OrderItemPhotoForm,
    extra=0,
    can_delete=True
)




#Create Dynamic Measurement Form Loader

def get_measurement_form(product_type):
    model_name = product_type.measurement_model

    try:
        model = apps.get_model("orders", model_name)
    except LookupError:
        return None

    BaseForm = modelform_factory(
        model,
        exclude=("base",)
    )

    # 🔥 Create styled version of the form
    class StyledMeasurementForm(BaseForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            for field in self.fields.values():
                field.widget.attrs.update({
                    "class": "form-control"
                })

    return StyledMeasurementForm





class ClientPhotoForm(forms.ModelForm):

    photo_type = forms.ChoiceField(
        choices=ClientPhoto.PHOTO_TYPES,
        required=False,
        label="Photo Type"
    )

    image = forms.ImageField(
        required=False,
        label="Upload Photo",
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control",
            "accept": "image/*",
            
        })
    )

    class Meta:
        model = ClientPhoto
        fields = ["photo_type", "image"]
        


ClientPhotoFormSet = inlineformset_factory(
    Order,                # parent model
    ClientPhoto,          # child model
    form=ClientPhotoForm,
    extra=3,
    max_num=3,
    can_delete=False
)
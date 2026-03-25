from django.db import models
from .order_item import OrderItem
from PIL import Image, ExifTags

from django.core.files.base import ContentFile
from io import BytesIO


class OrderItemPhoto(models.Model):

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='photos',
        db_index=True
    )

    image = models.ImageField(upload_to='order_item_photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order_item.product_name} photo"
    


   


    def save(self, *args, **kwargs):

        if self.image:

            img = Image.open(self.image)

            try:
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break

                exif = getattr(img, "_getexif", lambda: None)()

                if exif is not None:
                    if exif.get(orientation) == 3:
                        img = img.rotate(180, expand=True)
                    elif exif.get(orientation) == 6:
                        img = img.rotate(270, expand=True)
                    elif exif.get(orientation) == 8:
                        img = img.rotate(90, expand=True)
            except:
                pass

            img.thumbnail((1200, 1200))

            # Fix color mode issue
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buffer = BytesIO()
            img.save(buffer, format="JPEG", optimize=True, quality=70)

            self.image.save(self.image.name, ContentFile(buffer.getvalue()), save=False)

        super().save(*args, **kwargs)
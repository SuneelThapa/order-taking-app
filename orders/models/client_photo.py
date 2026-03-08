from django.db import models
from .order import Order
from PIL import Image, ExifTags


class ClientPhoto(models.Model):

    PHOTO_TYPES = [
        ('front', 'Front'),
        ('side', 'Side'),
        ('back', 'Back'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='client_photos'
    )

    photo_type = models.CharField(max_length=20, choices=PHOTO_TYPES)
    image = models.ImageField(upload_to='client_photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'photo_type')

    def __str__(self):
        return f"{self.order.order_number} - {self.photo_type}"
    


    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

        if self.image and hasattr(self.image, "path"):

            img = Image.open(self.image.path)

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
            img.save(self.image.path, optimize=True, quality=70)
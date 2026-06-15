from django.db import models
from PIL import Image, ExifTags
from django.core.files.base import ContentFile
from io import BytesIO

from .order import Order


class ClientPhoto(models.Model):

    PHOTO_TYPES = [
        ('front', 'Front'),
        ('side', 'Side'),
        ('back', 'Back'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='client_photos',
        db_index=True
    )
    person_number = models.PositiveIntegerField(
        default=1,
        help_text="Person 1, 2, 3... for package orders with multiple people."
    )
    photo_type = models.CharField(max_length=20, choices=PHOTO_TYPES)
    image = models.ImageField(upload_to='client_photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'person_number', 'photo_type')
        verbose_name = 'Client Photo'
        verbose_name_plural = 'Client Photos'

    def __str__(self):
        return f"{self.order.order_number} — Person {self.person_number} — {self.photo_type}"

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
            except Exception:
                pass
            img.thumbnail((1200, 1200))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", optimize=True, quality=70)
            self.image.save(self.image.name, ContentFile(buffer.getvalue()), save=False)
        super().save(*args, **kwargs)
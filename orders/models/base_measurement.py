from django.db import models



class BaseMeasurement(models.Model):
    order_item = models.OneToOneField(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name='measurement'
    )

    

    created_at = models.DateTimeField(auto_now_add=True)

    def get_specific_measurement(self):
        for attr in [
            'shirt',
            'jacket',
            'pants',
            'shorts',
            'skirt',
            'vest',
            'blouse',
            'dress',
        ]:
            if hasattr(self, attr):
                return attr, getattr(self, attr)
        return None, None

    
    def __str__(self):
        return str(self.order_item)
    

    def get_all_measurements(self):
        measurements = []

        for relation in self._meta.related_objects:

            if not relation.one_to_one:
                continue

            accessor_name = relation.get_accessor_name()

            try:
                related_obj = getattr(self, accessor_name)
            except relation.related_model.DoesNotExist:
                continue

            fields = []

            for field in related_obj._meta.fields:
                if field.name in ['id', 'basemeasurement_ptr', 'base']:
                    continue

                value = getattr(related_obj, field.name)

                if value is None or value == "":
                    continue

                fields.append({
                    "label": field.verbose_name.title(),
                    "value": value
                })

            measurements.append({
                "name": related_obj._meta.verbose_name.title(),
                "fields": fields,
            })

        return measurements





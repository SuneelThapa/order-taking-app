import uuid
from django.db import migrations, models


def generate_unique_tokens(apps, schema_editor):
    ProductionBill = apps.get_model('orders', 'ProductionBill')
    for bill in ProductionBill.objects.all():
        bill.share_token = uuid.uuid4()
        bill.save(update_fields=['share_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0016_orderitem_group_label'),
    ]

    operations = [
        # Step 1: Add column without unique constraint, nullable
        migrations.AddField(
            model_name='productionbill',
            name='share_token',
            field=models.UUIDField(
                null=True,
                blank=True,
                editable=False,
            ),
        ),
        # Step 2: Fill unique values for existing rows
        migrations.RunPython(
            generate_unique_tokens,
            migrations.RunPython.noop,
        ),
        # Step 3: Add unique constraint
        migrations.AlterField(
            model_name='productionbill',
            name='share_token',
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                editable=False,
                help_text='Token for public share link (no login required)',
            ),
        ),
    ]
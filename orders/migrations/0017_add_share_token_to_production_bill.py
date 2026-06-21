import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0016_orderitem_group_label'),
    ]

    operations = [
        migrations.AddField(
            model_name='productionbill',
            name='share_token',
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                editable=False,
                help_text='Token for public share link (no login required)'
            ),
        ),
    ]

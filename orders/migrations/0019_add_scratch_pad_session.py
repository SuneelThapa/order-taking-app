import uuid
import django.db.models.deletion
import django.utils.timezone
from datetime import timedelta
from django.db import migrations, models


def set_expires_at(apps, schema_editor):
    ScratchPadSession = apps.get_model('orders', 'ScratchPadSession')
    for s in ScratchPadSession.objects.filter(expires_at__isnull=True):
        s.expires_at = django.utils.timezone.now() + timedelta(minutes=30)
        s.save()


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0018_add_shoulder_to_back_and_waist'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScratchPadSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('mode', models.CharField(choices=[('contact', 'Contact Info'), ('measurements', 'Measurements')], max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processed', 'Processed')], default='pending', max_length=20)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('gender', models.CharField(blank=True, default='men', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
            ],
            options={
                'verbose_name': 'Scratch Pad Session',
                'verbose_name_plural': 'Scratch Pad Sessions',
                'ordering': ['-created_at'],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0023_tenant_whatsapp_catalogue'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='custom_domain',
            field=models.CharField(
                max_length=255, blank=True, default='',
                help_text="Client's own domain e.g. studio.sukhumvittailors.com"
            ),
        ),
    ]
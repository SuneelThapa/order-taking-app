from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0021_tenant_logo_favicon_package'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='whatsapp_token',
            field=models.TextField(
                blank=True, default='',
                help_text='WhatsApp Business API permanent token'
            ),
        ),
        migrations.AddField(
            model_name='tenant',
            name='whatsapp_phone_number_id',
            field=models.CharField(
                max_length=50, blank=True, default='',
                help_text='WhatsApp Phone Number ID from Meta Developer Dashboard'
            ),
        ),
        migrations.AddField(
            model_name='tenant',
            name='has_catalogue',
            field=models.BooleanField(
                default=False,
                help_text='Shop has catalogue app enabled'
            ),
        ),
        migrations.AddField(
            model_name='tenant',
            name='catalogue_subdomain',
            field=models.CharField(
                max_length=100, blank=True, default='',
                help_text='Catalogue subdomain'
            ),
        ),
        migrations.AddField(
            model_name='tenant',
            name='display_key',
            field=models.CharField(
                max_length=50, blank=True, default='',
                help_text='Secret key for status board URL e.g. shop2026'
            ),
        ),
    ]
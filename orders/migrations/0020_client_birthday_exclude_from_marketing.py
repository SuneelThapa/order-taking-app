from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0019_add_scratch_pad_session'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='birthday',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Optional — for birthday promotions',
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='exclude_from_marketing',
            field=models.BooleanField(
                default=False,
                help_text='Exclude from all promotional notifications (unhappy client, refund, etc.)',
            ),
        ),
    ]
# Generated by Django 2.2.14 on 2020-10-13 15:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0052_auto_20201013_1516'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentcardaccountimage',
            name='dark_mode_image',
            field=models.ImageField(blank=True, null=True, upload_to='schemes'),
        ),
        migrations.AddField(
            model_name='paymentcardimage',
            name='dark_mode_image',
            field=models.ImageField(blank=True, null=True, upload_to='schemes'),
        ),
    ]

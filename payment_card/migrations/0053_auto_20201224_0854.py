# Generated by Django 2.2.14 on 2020-12-24 08:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0052_auto_20201015_1202'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentcardaccountimage',
            name='call_to_action',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AlterField(
            model_name='paymentcardimage',
            name='call_to_action',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]

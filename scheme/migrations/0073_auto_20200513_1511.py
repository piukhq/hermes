# Generated by Django 2.2.11 on 2020-05-13 14:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0072_auto_20200331_1812'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemeaccount',
            name='barcode',
            field=models.CharField(blank=True, default='', max_length=250),
        ),
        migrations.AddField(
            model_name='schemeaccount',
            name='card_number',
            field=models.CharField(blank=True, default='', max_length=250),
        ),
    ]
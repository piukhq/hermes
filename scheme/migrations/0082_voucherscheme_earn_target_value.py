# Generated by Django 2.2.11 on 2020-07-31 11:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0081_schemeaccount_formatted_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='voucherscheme',
            name='earn_target_value',
            field=models.IntegerField(blank=True, help_text='Enter a value in this field if the merchant scheme does not return an earn.target_value for the voucher', null=True, verbose_name='Earn Target Value'),
        ),
    ]

# Generated by Django 2.2.14 on 2020-10-15 11:02

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0051_paymentcardaccount_pll_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentcardaccountimage",
            name="dark_mode_image",
            field=models.ImageField(blank=True, null=True, upload_to="schemes"),
        ),
        migrations.AddField(
            model_name="paymentcardaccountimage",
            name="dark_mode_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="paymentcardimage",
            name="dark_mode_image",
            field=models.ImageField(blank=True, null=True, upload_to="schemes"),
        ),
        migrations.AddField(
            model_name="paymentcardimage",
            name="dark_mode_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]

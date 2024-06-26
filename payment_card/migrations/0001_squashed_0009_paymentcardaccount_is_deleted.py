# Generated by Django 1.9.1 on 2016-02-01 10:21

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    replaces = [
        ("payment_card", "0001_initial"),
        ("payment_card", "0002_auto_20150917_1729"),
        ("payment_card", "0003_auto_20150923_1044"),
        ("payment_card", "0004_auto_20151016_1330"),
        ("payment_card", "0005_paymentcardaccount_token"),
        ("payment_card", "0006_auto_20151110_1130"),
        ("payment_card", "0007_auto_20151110_1211"),
        ("payment_card", "0008_auto_20151126_1341"),
        ("payment_card", "0009_paymentcardaccount_is_deleted"),
    ]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Issuer",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("image", models.ImageField(upload_to="")),
            ],
        ),
        migrations.CreateModel(
            name="PaymentCard",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(unique=True)),
                ("url", models.URLField()),
                ("image", models.ImageField(null=True, upload_to="")),
                ("scan_message", models.CharField(max_length=100)),
                ("input_label", models.CharField(max_length=150)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "system",
                    models.CharField(
                        choices=[("visa", "Visa"), ("mastercard", "Master Card"), ("amex", "American Express\u200e")],
                        max_length=40,
                    ),
                ),
                ("type", models.CharField(choices=[("debit", "Debit Card"), ("credit", "Credit Card")], max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name="PaymentCardAccount",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name_on_card", models.CharField(max_length=150)),
                ("start_month", models.IntegerField(null=True)),
                ("start_year", models.IntegerField(null=True)),
                ("expiry_month", models.IntegerField()),
                ("expiry_year", models.IntegerField()),
                ("status", models.IntegerField(choices=[(0, "pending"), (1, "active")], default=0)),
                ("order", models.IntegerField(default=0)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("issuer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="payment_card.Issuer")),
                (
                    "payment_card",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="payment_card.PaymentCard"),
                ),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("token", models.CharField(default="test", max_length=255)),
                ("country", models.CharField(default="United Kingdom", max_length=40)),
                ("currency_code", models.CharField(default="GBP", max_length=3)),
                ("pan_end", models.CharField(max_length=6)),
                ("pan_start", models.CharField(max_length=6)),
                ("is_deleted", models.BooleanField(default=False)),
            ],
        ),
        migrations.AlterField(
            model_name="paymentcard",
            name="image",
            field=models.ImageField(default=1, upload_to=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="issuer",
            name="image",
            field=models.ImageField(upload_to="issuers"),
        ),
        migrations.AlterField(
            model_name="paymentcard",
            name="image",
            field=models.ImageField(upload_to="payment_cards"),
        ),
    ]

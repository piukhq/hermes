# Generated by Django 2.2.6 on 2019-10-18 14:10

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0064_auto_20191015_1455"),
    ]

    operations = [
        migrations.AddField(
            model_name="schemeaccount",
            name="vouchers",
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.CreateModel(
            name="VoucherScheme",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("earn_currency", models.CharField(blank=True, max_length=50, verbose_name="Currency")),
                ("earn_prefix", models.CharField(blank=True, max_length=50, verbose_name="Prefix")),
                ("earn_suffix", models.CharField(blank=True, max_length=50, verbose_name="Suffix")),
                (
                    "earn_type",
                    models.CharField(
                        choices=[("join", "Join"), ("accumulator", "Accumulator")],
                        max_length=50,
                        verbose_name="Earn Type",
                    ),
                ),
                ("burn_currency", models.CharField(blank=True, max_length=50, verbose_name="Currency")),
                ("burn_prefix", models.CharField(blank=True, max_length=50, verbose_name="Prefix")),
                ("burn_suffix", models.CharField(blank=True, max_length=50, verbose_name="Suffix")),
                (
                    "burn_type",
                    models.CharField(
                        choices=[("voucher", "Voucher"), ("coupon", "Coupon"), ("discount", "Discount")],
                        max_length=50,
                        verbose_name="Burn Type",
                    ),
                ),
                ("burn_value", models.FloatField(blank=True, null=True, verbose_name="Value")),
                (
                    "barcode_type",
                    models.IntegerField(
                        choices=[
                            (0, "CODE128 (B or C)"),
                            (1, "QrCode"),
                            (2, "AztecCode"),
                            (3, "Pdf417"),
                            (4, "EAN (13)"),
                            (5, "DataMatrix"),
                            (6, "ITF (Interleaved 2 of 5)"),
                            (7, "Code 39"),
                        ]
                    ),
                ),
                ("headline_inprogress", models.CharField(max_length=250, verbose_name="In Progress")),
                ("headline_expired", models.CharField(max_length=250, verbose_name="Expired")),
                ("headline_redeemed", models.CharField(max_length=250, verbose_name="Redeemed")),
                ("headline_issued", models.CharField(max_length=250, verbose_name="Issued")),
                ("subtext", models.CharField(max_length=250)),
                ("expiry_months", models.IntegerField()),
                ("scheme", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="scheme.Scheme")),
            ],
        ),
    ]

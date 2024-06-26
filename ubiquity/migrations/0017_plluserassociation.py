# Generated by Django 4.0.7 on 2022-11-29 14:27

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ubiquity", "0016_alter_schemeaccountentry_link_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="PllUserAssociation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state", models.IntegerField(choices=[(0, "pending"), (1, "active"), (2, "inactive")], default=0)),
                (
                    "slug",
                    models.SlugField(
                        blank=True,
                        choices=[
                            ("LOYALTY_CARD_PENDING", "LOYALTY_CARD_PENDING"),
                            ("LOYALTY_CARD_NOT_AUTHORISED", "LOYALTY_CARD_NOT_AUTHORISED"),
                            ("PAYMENT_ACCOUNT_PENDING", "PAYMENT_ACCOUNT_PENDING"),
                            ("PAYMENT_ACCOUNT_INACTIVE", "PAYMENT_ACCOUNT_INACTIVE"),
                            ("PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE", "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE"),
                            ("PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING", "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING"),
                            ("UBIQUITY_COLLISION", "UBIQUITY_COLLISION"),
                        ],
                        default="",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "pll",
                    models.ForeignKey(
                        default=None,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="ubiquity.paymentcardschemeentry",
                        verbose_name="Associated PLL",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Associated User",
                    ),
                ),
            ],
            options={
                "unique_together": {("pll", "user")},
            },
        ),
    ]

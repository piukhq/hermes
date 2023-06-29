# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-11-07 11:58
from __future__ import unicode_literals

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payment_card", "0037_auto_20181016_1110"),
        ("user", "0031_customuser_salt"),
        ("scheme", "0051_auto_20181107_1158"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentCardAccountEntry",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "payment_card_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="payment_card.PaymentCardAccount"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PaymentCardSchemeEntry",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active_link", models.BooleanField(default=True)),
                (
                    "payment_card_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="payment_card.PaymentCardAccount"
                    ),
                ),
                (
                    "scheme_account",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="scheme.SchemeAccount"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SchemeAccountEntry",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "scheme_account",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="scheme.SchemeAccount"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ServiceConsent",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("timestamp", models.DateTimeField()),
            ],
        ),
        migrations.AddField(
            model_name="schemeaccountentry",
            name="user",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="paymentcardaccountentry",
            name="user",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name="schemeaccountentry",
            unique_together=set([("scheme_account", "user")]),
        ),
        migrations.AlterUniqueTogether(
            name="paymentcardschemeentry",
            unique_together=set([("payment_card_account", "scheme_account")]),
        ),
        migrations.AlterUniqueTogether(
            name="paymentcardaccountentry",
            unique_together=set([("payment_card_account", "user")]),
        ),
    ]

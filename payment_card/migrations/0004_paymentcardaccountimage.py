# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-04-08 13:51
from __future__ import unicode_literals

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment_card", "0003_auto_20160218_1616"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentCardAccountImage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "image_type_code",
                    models.IntegerField(
                        choices=[(0, "hero"), (1, "banner"), (2, "offers"), (3, "icon"), (4, "asset"), (5, "reference")]
                    ),
                ),
                ("size_code", models.CharField(blank=True, max_length=30, null=True)),
                ("image", models.ImageField(upload_to="schemes")),
                ("strap_line", models.CharField(blank=True, max_length=50, null=True)),
                ("description", models.CharField(blank=True, max_length=300, null=True)),
                ("url", models.URLField(blank=True, null=True)),
                ("call_to_action", models.CharField(max_length=150)),
                ("order", models.IntegerField()),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]

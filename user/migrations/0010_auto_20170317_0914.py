# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-03-17 09:14
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0009_auto_20160817_0953"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketingCode",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(blank=True, max_length=100, null=True)),
                ("date_from", models.DateTimeField()),
                ("date_to", models.DateTimeField()),
                ("description", models.CharField(blank=True, max_length=300, null=True)),
                ("partner", models.CharField(blank=True, max_length=100, null=True)),
            ],
        ),
        migrations.AddField(
            model_name="customuser",
            name="marketing_code",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="user.MarketingCode"
            ),
        ),
    ]

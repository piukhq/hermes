# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-01-09 10:26
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0033_auto_20190108_1601"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="clientapplicationbundle",
            unique_together=set([("client", "bundle_id")]),
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-03-22 10:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0036_auto_20190320_1206'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientapplicationbundle',
            name='scheme',
            field=models.ManyToManyField(blank=True, related_name='related_bundle', through='scheme.SchemeBundleAssociation', to='scheme.Scheme'),
        ),
    ]

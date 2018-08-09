# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-08-09 09:39
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0054_auto_20180808_1549'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchemeDetails',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.IntegerField(choices=[(0, 'Tier')], default=0)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('scheme_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.Scheme')),
            ],
        ),
    ]

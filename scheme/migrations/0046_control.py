# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-09-25 08:19
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0045_schemeaccount_join_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='Control',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(choices=[('join_button', 'Join Button - Add Card screen'), ('add_button', 'Add Button - Add Card screen')], max_length=50)),
                ('label', models.CharField(blank=True, max_length=50)),
                ('hint_text', models.CharField(blank=True, max_length=250)),
                ('scheme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='controls', to='scheme.Scheme')),
            ],
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-03-27 09:38
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0017_data_bink_org_and_clientapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='client',
            field=models.ForeignKey(default='MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd', on_delete=django.db.models.deletion.CASCADE, to='user.ClientApplication'),
        ),
    ]

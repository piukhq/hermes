# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-09-16 09:06
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0063_voucherscheme'),
    ]

    operations = [
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(choices=[('issued', 'Issued'), ('inprogress', 'In Progress'), ('redeemed', 'Redeemed'), ('expired', 'Expired')], max_length=50)),
                ('code', models.CharField(max_length=50)),
                ('issue_date', models.DateTimeField()),
                ('expiry_date', models.DateTimeField()),
                ('scheme_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.SchemeAccount')),
                ('voucher_scheme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.VoucherScheme')),
            ],
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Scheme',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('name', models.CharField(max_length=200)),
                ('url', models.URLField()),
                ('company', models.CharField(max_length=200)),
                ('company_url', models.URLField()),
                ('tier', models.IntegerField()),
                ('barcode_type', models.IntegerField()),
                ('scan_message', models.CharField(max_length=100)),
                ('point_name', models.CharField(max_length=50, default='points')),
                ('point_conversion_rate', models.DecimalField(decimal_places=10, max_digits=20)),
                ('input_label', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='SchemeAccount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('username', models.CharField(max_length=150)),
                ('card_number', models.CharField(max_length=50)),
                ('membership_number', models.CharField(max_length=50)),
                ('password', models.CharField(max_length=30)),
                ('status', models.IntegerField()),
                ('order', models.IntegerField()),
                ('is_valid', models.BooleanField()),
                ('created', models.DateTimeField()),
                ('updated', models.DateTimeField()),
                ('scheme', models.ForeignKey(to='scheme.Scheme')),
            ],
        ),
        migrations.CreateModel(
            name='SchemeAccountSecurityQuestion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('question', models.CharField(max_length=250)),
                ('answer', models.CharField(max_length=250)),
                ('scheme_account_id', models.ForeignKey(to='scheme.SchemeAccount')),
            ],
        ),
        migrations.CreateModel(
            name='SchemeImage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('image_type_code', models.IntegerField()),
                ('is_barcode', models.BooleanField()),
                ('identifier', models.CharField(max_length=30)),
                ('size_code', models.CharField(max_length=30)),
                ('image_path', models.CharField(max_length=300)),
                ('strap_line', models.CharField(max_length=50)),
                ('description', models.CharField(max_length=300)),
                ('url', models.URLField()),
                ('call_to_action', models.CharField(max_length=50)),
                ('order', models.IntegerField()),
                ('is_published', models.BooleanField()),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField()),
                ('is_deleted', models.BooleanField()),
                ('created', models.DateTimeField()),
                ('scheme_id', models.ForeignKey(to='scheme.Scheme')),
            ],
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Scheme',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(unique=True)),
                ('url', models.URLField()),
                ('company', models.CharField(max_length=200)),
                ('company_url', models.URLField()),
                ('tier', models.IntegerField(choices=[(1, 'Tier 1'), (2, 'Tier 2')])),
                ('barcode_type', models.IntegerField()),
                ('scan_message', models.CharField(max_length=100)),
                ('point_name', models.CharField(default='points', max_length=50)),
                ('point_conversion_rate', models.DecimalField(decimal_places=6, max_digits=20)),
                ('input_label', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('category', models.ForeignKey(to='scheme.Category')),
            ],
        ),
        migrations.CreateModel(
            name='SchemeAccount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('username', models.CharField(max_length=150)),
                ('card_number', models.CharField(max_length=50)),
                ('membership_number', models.CharField(blank=True, max_length=50, null=True)),
                ('password', models.TextField()),
                ('status', models.IntegerField(default=0, choices=[(0, 'pending'), (1, 'active'), (2, 'invalid credentials'), (3, 'end site down'), (4, 'deleted')])),
                ('order', models.IntegerField(default=0)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('scheme', models.ForeignKey(to='scheme.Scheme')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SchemeAccountSecurityQuestion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('question', models.CharField(max_length=250)),
                ('answer', models.CharField(max_length=250)),
                ('scheme_account_id', models.ForeignKey(to='scheme.SchemeAccount')),
            ],
        ),
        migrations.CreateModel(
            name='SchemeImage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
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
                ('status', models.IntegerField(default=0, choices=[(0, 'draft'), (1, 'published')])),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('scheme_id', models.ForeignKey(to='scheme.Scheme')),
            ],
        ),
    ]

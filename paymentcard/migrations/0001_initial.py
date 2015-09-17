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
            name='Issuer',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('image', models.ImageField(upload_to='')),
            ],
        ),
        migrations.CreateModel(
            name='PaymentCard',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(unique=True)),
                ('url', models.URLField()),
                ('image', models.ImageField(upload_to='', null=True)),
                ('scan_message', models.CharField(max_length=100)),
                ('input_label', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('system', models.CharField(max_length=40, choices=[('visa', 'Visa'), ('mastercard', 'Master Card'), ('amex', 'American Express\u200e')])),
                ('type', models.CharField(max_length=40, choices=[('debit', 'Debit Card'), ('credit', 'Credit Card')])),
            ],
        ),
        migrations.CreateModel(
            name='PaymentCardAccount',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('name_on_card', models.CharField(max_length=150)),
                ('start_month', models.IntegerField(null=True)),
                ('start_year', models.IntegerField(null=True)),
                ('expiry_month', models.IntegerField()),
                ('expiry_year', models.IntegerField()),
                ('pan', models.CharField(max_length=50)),
                ('status', models.IntegerField(default=0, choices=[(0, 'pending'), (1, 'active'), (2, 'invalid credentials'), (3, 'end site down'), (4, 'deleted')])),
                ('order', models.IntegerField(default=0)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('postcode', models.CharField(null=True, max_length=20, blank=True)),
                ('security_code', models.CharField(max_length=6)),
                ('issuer', models.ForeignKey(to='paymentcard.Issuer')),
                ('payment_card', models.ForeignKey(to='paymentcard.PaymentCard')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

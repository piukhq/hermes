# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-07-03 10:32
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ubiquity', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scheme', '0048_remove_schemeaccount_user'),
        ('payment_card', '0037_remove_paymentcardaccount_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentcardaccount',
            name='scheme_account_set',
            field=models.ManyToManyField(related_name='payment_card_account_set', through='ubiquity.PaymentCardSchemeEntry', to='scheme.SchemeAccount'),
        ),
        migrations.AddField(
            model_name='paymentcardaccount',
            name='user_set',
            field=models.ManyToManyField(related_name='payment_card_account_set', through='ubiquity.PaymentCardAccountEntry', to=settings.AUTH_USER_MODEL),
        ),
    ]

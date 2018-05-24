# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2018-05-24 15:46
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0041_auto_20180524_0958'),
        ('user', '0032_auto_20180524_0958'),
        ('payment_card', '0034_auto_20180129_1405'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentCardAccountEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='PaymentCardSchemeEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.RemoveField(
            model_name='paymentcardaccount',
            name='user',
        ),
        migrations.AddField(
            model_name='paymentcardschemeentry',
            name='payment_card_account',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='payment_card.PaymentCardAccount'),
        ),
        migrations.AddField(
            model_name='paymentcardschemeentry',
            name='scheme_account',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheme.SchemeAccount'),
        ),
        migrations.AddField(
            model_name='paymentcardaccountentry',
            name='payment_card_account',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='payment_card.PaymentCardAccount'),
        ),
        migrations.AddField(
            model_name='paymentcardaccountentry',
            name='prop',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='user.Property'),
        ),
        migrations.AddField(
            model_name='paymentcardaccount',
            name='prop_set',
            field=models.ManyToManyField(related_name='payment_card_account_set', through='payment_card.PaymentCardAccountEntry', to='user.Property'),
        ),
        migrations.AddField(
            model_name='paymentcardaccount',
            name='scheme_account_set',
            field=models.ManyToManyField(related_name='payment_card_account_set', through='payment_card.PaymentCardSchemeEntry', to='scheme.SchemeAccount'),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0005_paymentcardaccount_token'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='paymentcardaccount',
            name='pan',
        ),
        migrations.RemoveField(
            model_name='paymentcardaccount',
            name='postcode',
        ),
        migrations.RemoveField(
            model_name='paymentcardaccount',
            name='security_code',
        ),
        migrations.AddField(
            model_name='paymentcardaccount',
            name='country',
            field=models.CharField(max_length=40, default='United Kingdom'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='paymentcardaccount',
            name='currency_code',
            field=models.CharField(max_length=3, default='GBP'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='paymentcardaccount',
            name='pan_end',
            field=models.PositiveIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='paymentcardaccount',
            name='pan_start',
            field=models.PositiveIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='status',
            field=models.IntegerField(choices=[(0, 'pending'), (1, 'active')], default=0),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0004_auto_20151016_1330'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentcardaccount',
            name='token',
            field=models.CharField(default='test', max_length=255),
            preserve_default=False,
        ),
    ]

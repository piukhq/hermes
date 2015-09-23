# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0002_auto_20150917_1729'),
    ]

    operations = [
        migrations.AlterField(
            model_name='issuer',
            name='image',
            field=models.ImageField(upload_to='issuers'),
        ),
        migrations.AlterField(
            model_name='paymentcard',
            name='image',
            field=models.ImageField(upload_to='payment_cards'),
        ),
    ]

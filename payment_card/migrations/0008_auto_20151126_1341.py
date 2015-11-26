# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import payment_card.models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0007_auto_20151110_1211'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='pan_end',
            field=models.CharField(max_length=6),
        ),
    ]

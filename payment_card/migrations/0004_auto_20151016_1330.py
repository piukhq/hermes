# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import payment_card.models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0003_auto_20150923_1044'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='pan',
            field=models.CharField(max_length=50),
        ),
    ]

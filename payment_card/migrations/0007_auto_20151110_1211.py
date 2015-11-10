# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import payment_card.models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0006_auto_20151110_1130'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='pan_end',
            field=models.CharField(max_length=4, validators=[payment_card.models.validate_pan_end]),
        ),
        migrations.AlterField(
            model_name='paymentcardaccount',
            name='pan_start',
            field=models.CharField(max_length=6, validators=[payment_card.models.validate_pan_start]),
        ),
    ]

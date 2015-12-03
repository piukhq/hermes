# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0008_auto_20151126_1341'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentcardaccount',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]

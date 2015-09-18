# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payment_card', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentcard',
            name='image',
            field=models.ImageField(upload_to='', default=1),
            preserve_default=False,
        ),
    ]

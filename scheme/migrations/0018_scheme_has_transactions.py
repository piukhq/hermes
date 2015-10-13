# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0017_auto_20151012_1328'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='has_transactions',
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
    ]

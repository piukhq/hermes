# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0018_scheme_has_transactions'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='has_points',
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
    ]

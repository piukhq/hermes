# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0004_auto_20150922_1421'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='forgotten_password_url',
            field=models.URLField(max_length=500),
        ),
    ]

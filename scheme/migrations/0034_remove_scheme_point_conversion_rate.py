# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0033_auto_20151109_1021'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scheme',
            name='point_conversion_rate',
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0048_auto_20160118_1104'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scheme',
            name='manual_question',
        ),
        migrations.RemoveField(
            model_name='scheme',
            name='scan_question',
        ),
    ]

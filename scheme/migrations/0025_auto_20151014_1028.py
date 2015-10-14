# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0024_auto_20151014_1019'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='identifier',
            field=models.CharField(blank=True, null=True, max_length=30),
        ),
    ]

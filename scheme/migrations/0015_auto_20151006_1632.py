# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0014_auto_20151006_1351'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='company_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='scheme',
            name='slug',
            field=models.SlugField(unique=True),
        ),
    ]

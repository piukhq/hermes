# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0004_auto_20150922_1421'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='schemeimage',
            name='image_path',
        ),
        migrations.AddField(
            model_name='schemeimage',
            name='image',
            field=models.ImageField(upload_to='schemes', default=''),
            preserve_default=False,
        ),
    ]

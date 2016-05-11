# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0002_auto_20150916_1255'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='forgotten_password_url',
            field=models.URLField(default='http://www.google.com'),
            preserve_default=False,
        ),
    ]

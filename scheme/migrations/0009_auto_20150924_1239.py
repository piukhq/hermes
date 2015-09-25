# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0008_auto_20150924_1059'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemecredentialquestion',
            name='slug',
            field=models.CharField(max_length=250),
        ),
    ]

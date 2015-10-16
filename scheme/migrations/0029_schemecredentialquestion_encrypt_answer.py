# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0028_auto_20151015_1332'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='encrypt_answer',
            field=models.BooleanField(default=False),
        ),
    ]

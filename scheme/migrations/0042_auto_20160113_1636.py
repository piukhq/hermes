# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0041_auto_20160112_1731'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scheme',
            name='primary_question',
        ),
        migrations.AddField(
            model_name='scheme',
            name='manual_question',
            field=models.ForeignKey(null=True, related_name='manual_question', to='scheme.SchemeCredentialQuestion', blank=True),
        ),
    ]

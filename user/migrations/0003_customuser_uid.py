# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_customuser_is_staff'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='uid',
            field=models.CharField(max_length=50, blank=True, null=True),
        ),
    ]

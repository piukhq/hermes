# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0041_auto_20160112_1731'),
    ]

    operations = [
        migrations.RenameField('scheme', 'primary_question', 'manual_question'),
    ]

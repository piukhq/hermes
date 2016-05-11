# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0029_schemecredentialquestion_encrypt_answer'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='schemecredentialquestion',
            name='encrypt_answer',
        ),
    ]

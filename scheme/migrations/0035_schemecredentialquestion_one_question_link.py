# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-06-28 13:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0034_auto_20170619_1552'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='one_question_link',
            field=models.BooleanField(default=False),
        ),
    ]

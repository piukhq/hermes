# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0046_auto_20160115_1001'),
    ]

    operations = [
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='manual_question',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='schemecredentialquestion',
            name='scan_question',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='scheme',
            name='manual_question',
            field=models.ForeignKey(to='scheme.SchemeCredentialQuestion', null=True, blank=True, related_name='manual_question_old'),
        ),
        migrations.AlterField(
            model_name='scheme',
            name='scan_question',
            field=models.ForeignKey(to='scheme.SchemeCredentialQuestion', null=True, blank=True, related_name='scan_question_old'),
        ),
    ]

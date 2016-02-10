# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0039_remove_schemeaccountcredentialanswer_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemeaccountcredentialanswer',
            name='question',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, null=True, to='scheme.SchemeCredentialQuestion'),
        ),
        migrations.AlterUniqueTogether(
            name='schemecredentialquestion',
            unique_together=set([('scheme', 'type')]),
        ),
    ]

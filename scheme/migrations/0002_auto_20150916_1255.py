# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='schemeaccountsecurityquestion',
            old_name='scheme_account_id',
            new_name='scheme_account',
        ),
        migrations.RenameField(
            model_name='schemeimage',
            old_name='scheme_id',
            new_name='scheme',
        ),
    ]

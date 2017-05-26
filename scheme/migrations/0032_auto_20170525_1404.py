# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-25 14:04
from __future__ import unicode_literals

from django.db import migrations


def update_link_dates(apps, schema_editor):
    # Update link_date for existing scheme accounts
    scheme_accounts = apps.get_model('scheme', 'SchemeAccount').objects.filter(status=1)
    for scheme_account in scheme_accounts:
        if not scheme_account.link_date:
            scheme_account.link_date = scheme_account.created
            scheme_account.save()


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0031_auto_20170525_1402'),
    ]

    operations = [
        migrations.RunPython(update_link_dates, migrations.RunPython.noop)
    ]

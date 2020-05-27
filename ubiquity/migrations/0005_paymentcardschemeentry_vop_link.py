# Generated by Django 2.2.11 on 2020-05-21 14:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ubiquity', '0004_auto_20190311_1158'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentcardschemeentry',
            name='vop_link',
            field=models.IntegerField(choices=[(0, 'undefined'), (1, 'activating'), (2, 'deactivating'), (3, 'activated')], default=0, help_text='The status of VOP card activation'),
        ),
    ]

# Generated by Django 2.2.19 on 2021-03-24 15:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0091_optional_call_to_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheme',
            name='tier',
            field=models.IntegerField(choices=[(1, 'PLL'), (2, 'Basic'), (3, 'Partner'), (4, 'Coming Soon')]),
        ),
    ]

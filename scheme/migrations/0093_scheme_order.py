# Generated by Django 2.2.14 on 2021-05-07 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheme', '0092_auto_20210324_1518'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheme',
            name='order',
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True),
        ),
    ]
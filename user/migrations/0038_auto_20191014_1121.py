# Generated by Django 2.2.6 on 2019-10-14 10:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0037_customuser_is_tester'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='marketing_code',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='user.MarketingCode'),
        ),
    ]

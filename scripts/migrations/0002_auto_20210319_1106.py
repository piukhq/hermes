# Generated by Django 2.2.14 on 2021-03-19 11:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scripts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Correction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.AlterField(
            model_name='scriptresult',
            name='apply',
            field=models.IntegerField(choices=[(0, 'No correction available'), (1, 'Mark as deactivated as same token is also active'), (2, 'VOP Activate'), (3, 'Re-enrol, VOP Deactivate, Un-enroll'), (4, 'Re-enroll'), (5, 'VOP Deactivate'), (6, 'Un-enroll')], db_index=True, default=0, help_text='Correction to Apply Now'),
        ),
        migrations.AlterField(
            model_name='scriptresult',
            name='correction',
            field=models.IntegerField(choices=[(0, 'No correction available'), (1, 'Mark as deactivated as same token is also active'), (2, 'VOP Activate'), (3, 'Re-enrol, VOP Deactivate, Un-enroll'), (4, 'Re-enroll'), (5, 'VOP Deactivate'), (6, 'Un-enroll')], db_index=True, default=0, help_text='Correction Required'),
        ),
    ]
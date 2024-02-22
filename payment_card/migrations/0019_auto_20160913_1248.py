# Generated by Django 1.9.2 on 2016-09-13 12:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payment_card", "0018_auto_20160831_1505"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentcard",
            name="token_method",
            field=models.IntegerField(choices=[(0, "Copy PSP token"), (1, "Generate length-24 token")], default=0),
        ),
        migrations.AddField(
            model_name="paymentcardaccount",
            name="psp_token",
            field=models.CharField(default="psp_token", max_length=255),
            preserve_default=False,
        ),
    ]

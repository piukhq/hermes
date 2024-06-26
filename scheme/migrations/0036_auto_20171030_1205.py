# Generated by Django 1.11.1 on 2017-10-30 12:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheme", "0035_schemecredentialquestion_one_question_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="schemecredentialquestion",
            name="join_question",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="schemeaccount",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "Pending"),
                    (1, "Active"),
                    (403, "Invalid credentials"),
                    (432, "Invalid mfa"),
                    (530, "End site down"),
                    (531, "IP blocked"),
                    (532, "Tripped captcha"),
                    (5, "Please check your scheme account login details."),
                    (434, "Account locked on end site"),
                    (429, "Cannot connect, too many retries"),
                    (520, "An unknown error has occurred"),
                    (9, "Midas unavailable"),
                    (10, "Wallet only card"),
                    (404, "Agent does not exist on midas"),
                    (533, "Password expired"),
                    (900, "Join"),
                    (901, "Join failed"),
                ],
                default=0,
            ),
        ),
    ]

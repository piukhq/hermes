# Generated by Django 2.2.24 on 2021-08-24 13:40

from django.db import migrations, models


def unauthorise_wallet_only_links(apps, schema_editor):
    SchemeAccountEntry = apps.get_model("ubiquity", "SchemeAccountEntry")
    wallet_only_card_links = SchemeAccountEntry.objects.filter(
        scheme_account__status=10,  # Wallet only status
    )

    wallet_only_card_links.update(auth_provided=False)


def revert_unauthorise_wallet_only_links(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("ubiquity", "0009_auto_20201007_1552"),
    ]

    operations = [
        migrations.AddField(
            model_name="schemeaccountentry",
            name="auth_provided",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(unauthorise_wallet_only_links, reverse_code=revert_unauthorise_wallet_only_links),
    ]

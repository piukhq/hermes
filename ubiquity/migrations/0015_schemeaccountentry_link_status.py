# Generated by Django 4.0.5 on 2022-08-30 13:25

from django.db import migrations, models

import ubiquity.models


def populate_link_status(apps, *stuff):
    # get the models from the app argument passed through the migration
    SchemeAccountEntry = apps.get_model("ubiquity", "SchemeAccountEntry")

    # ap = false first, wallet only cards
    ap_false_entries = SchemeAccountEntry.objects.filter(auth_provided=False)
    ap_false_entries.update(link_status=ubiquity.models.AccountLinkStatus["WALLET_ONLY"])

    # ap = True now...
    bulk_update_cache = []
    for entry in SchemeAccountEntry.objects.filter(auth_provided=True).select_related("scheme_account"):
        entry.link_status = entry.scheme_account.status
        bulk_update_cache.append(entry)

    # save all the things
    SchemeAccountEntry.objects.bulk_update(bulk_update_cache, ["link_status"])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("ubiquity", "0014_update_active_link_slugs"),
        ("scheme", "0109_alter_schemeaccountcredentialanswer_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="schemeaccountentry",
            name="link_status",
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
                    (503, "Too many balance requests running"),
                    (520, "An unknown error has occurred"),
                    (9, "Midas unavailable"),
                    (10, "Wallet only card"),
                    (404, "Agent does not exist on midas"),
                    (533, "Password expired"),
                    (900, "Join"),
                    (444, "No user currently found"),
                    (536, "Error with the configuration or it was not possible to retrieve"),
                    (535, "Request was not sent"),
                    (445, "Account already exists"),
                    (537, "Service connection error"),
                    (401, "Failed validation"),
                    (406, "Pre-registered card"),
                    (446, "Update failed. Delete and re-add card."),
                    (204, "Pending manual check."),
                    (436, "Invalid card_number"),
                    (437, "You can only Link one card per day."),
                    (438, "Unknown Card number"),
                    (439, "General Error such as incorrect user details"),
                    (441, "Join in progress"),
                    (538, "A system error occurred during join"),
                    (447, "The scheme has requested this account should be deleted"),
                    (442, "Asynchronous join in progress"),
                    (443, "Asynchronous registration in progress"),
                    (901, "Enrol Failed"),
                    (902, "Ghost Card Registration Failed"),
                    (1001, "Add and Auth pending"),
                    (2001, "Auth pending"),
                ],
                default=ubiquity.models.AccountLinkStatus["PENDING"],
            ),
        ),
        # data population, do not need a reverse as the field will be removed if we un-migrate
        migrations.RunPython(populate_link_status),
    ]

# Generated by Django 4.0.6 on 2022-07-27 07:32

import django.db.models.deletion
from django.db import migrations, models


def populate_answers(apps, *stuff):
    # get the models from the app argument passed through the migration
    SchemeAccountCredentialAnswer = apps.get_model("scheme", "SchemeAccountCredentialAnswer")
    SchemeAccountEntry = apps.get_model("ubiquity", "SchemeAccountEntry")

    for entry_id, scheme_account_id, user_id, auth_provided, link_status in SchemeAccountEntry.objects.values_list():
        ## fetch the answers for this scheme account
        answers = SchemeAccountCredentialAnswer.objects.filter(
            scheme_account_id=scheme_account_id, scheme_account_entry__isnull=True
        ).values()
        bulk_answers = []
        for answer in answers:
            saca = SchemeAccountCredentialAnswer(
                scheme_account_id=answer.get("scheme_account_id"),
                question_id=answer.get("question_id"),
                answer=answer.get("answer"),
                scheme_account_entry_id=entry_id,
            )
            bulk_answers.append(saca)
            if len(bulk_answers) > 999:
                SchemeAccountCredentialAnswer.objects.bulk_create(bulk_answers)
                bulk_answers = []
        SchemeAccountCredentialAnswer.objects.bulk_create(bulk_answers)

    ## now clean up the answers table - remove all entries without scheme_account_entry
    SchemeAccountCredentialAnswer.objects.filter(scheme_account_entry__isnull=True).delete()


def depopulate_answers(apps, *stuff):
    SchemeAccountCredentialAnswer = apps.get_model("scheme", "SchemeAccountCredentialAnswer")

    old_answers = SchemeAccountCredentialAnswer.objects.distinct("scheme_account_id", "question_id").values()
    bulk_answers = []
    for answer in old_answers:
        saca = SchemeAccountCredentialAnswer(
            scheme_account_id=answer.get("scheme_account_id"),
            question_id=answer.get("question_id"),
            answer=answer.get("answer"),
        )
        bulk_answers.append(saca)

    ## now clean up the answers table - remove all entries WITH scheme_account_entry
    SchemeAccountCredentialAnswer.objects.filter(scheme_account_entry__isnull=False).delete()

    ## now save the updated data
    SchemeAccountCredentialAnswer.objects.bulk_create(bulk_answers)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("ubiquity", "0015_schemeaccountentry_link_status"),
        ("scheme", "0108_alter_schemeaccount_status_and_more"),
    ]

    operations = [
        # remove old constraint
        migrations.AlterUniqueTogether(
            name="schemeaccountcredentialanswer",
            unique_together=set(),
        ),
        # create the new entry id field as a FK
        migrations.AddField(
            model_name="schemeaccountcredentialanswer",
            name="scheme_account_entry",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE, to="ubiquity.schemeaccountentry"
            ),
        ),
        # this new field is a constraint
        migrations.AlterUniqueTogether(
            name="schemeaccountcredentialanswer",
            unique_together={("scheme_account_entry", "question")},
        ),
        # data population
        migrations.RunPython(populate_answers, reverse_code=depopulate_answers),
    ]

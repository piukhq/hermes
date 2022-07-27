# Generated by Django 4.0.6 on 2022-07-27 07:32

from django.db import migrations, models
import django.db.models.deletion

from scheme.models import SchemeAccountCredentialAnswer
from ubiquity.models import SchemeAccountEntry



def populate_answers(*stuff):
    # for each scheme account in schemeaccountcredentialanswer
    # scheme_accounts = SchemeAccountCredentialAnswer.objects.values_list("scheme_account_id", flat=True).distinct()

    for entry_id, scheme_account_id, user_id, auth_provided in SchemeAccountEntry.objects.values_list(): 
        ## fetch the answers for this scheme account, insert them back into the answers table with tyhe extra FK
        answers = SchemeAccountCredentialAnswer.objects.filter(scheme_account_id=scheme_account_id).values()
        for answer in answers:
            saca = SchemeAccountCredentialAnswer.objects.create(
                scheme_account_id=answer.get("scheme_account_id"),
                question_id=answer.get("question_id"), 
                answer=answer.get("answer"),
                scheme_account_entry=entry_id
            )
            # save every row... expensive
            saca.save()
    ## now clean up the answers table - remove all entries without scheme_account_entry

    ## now make scheme_account_entry not nullable


def depopulate_answers(*stuff):
    ## honestly I have no idea
    pass



class Migration(migrations.Migration):

    dependencies = [
        ('ubiquity', '0014_update_active_link_slugs'),
        ('scheme', '0106_alter_schemeoverrideerror_unique_together'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='schemeaccountcredentialanswer',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='schemeaccountcredentialanswer',
            name='scheme_account_entry',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ubiquity.schemeaccountentry'),
        ),
        migrations.AlterUniqueTogether(
            name='schemeaccountcredentialanswer',
            unique_together={('scheme_account_entry', 'question')},
        ),
        migrations.RunPython(populate_answers, reverse_code=depopulate_answers),
    ]



from django import forms

from payment_card.models import PaymentCard


class CSVUploadForm(forms.Form):
    emails = forms.FileField()
    scheme = forms.ModelChoiceField(queryset=PaymentCard.objects.all().order_by('name'))

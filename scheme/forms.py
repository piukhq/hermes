from django import forms
from scheme.models import Scheme


class CSVUploadForm(forms.Form):
    emails = forms.FileField()
    scheme = forms.ModelChoiceField(queryset=Scheme.objects.all().order_by('name'))

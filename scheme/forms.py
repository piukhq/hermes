from django import forms
from scheme.models import Scheme


class CSVUploadForm(forms.Form):
    emails = forms.FileField()
    # scheme = forms.ModelChoiceField(queryset=Scheme.objects.all().order_by('name'))
    # TODO: check this is okay. it replaces the commented line above.
    scheme = forms.ModelChoiceField(queryset=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scheme'].queryset = Scheme.objects.all().order_by('name')

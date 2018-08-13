from django import forms
from django.core.exceptions import ValidationError

from scheme.models import Scheme, Consent, JourneyTypes


class CSVUploadForm(forms.Form):
    emails = forms.FileField()
    # scheme = forms.ModelChoiceField(queryset=Scheme.objects.all().order_by('name'))
    # TODO: check this is okay. it replaces the commented line above.
    scheme = forms.ModelChoiceField(queryset=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scheme'].queryset = Scheme.objects.all().order_by('name')


class ConsentForm(forms.ModelForm):
    class Meta:
        model = Consent
        exclude = []

    def clean(self):
        cleaned_data = super(ConsentForm, self).clean()

        # check_box value from form input (create) or existing value from model instance (update).
        check_box = cleaned_data.get('check_box') or self.instance.check_box

        # Validate that the Consent is not a check box type for the Add journey
        if check_box and (cleaned_data['journey'] == JourneyTypes.ADD.value):
            raise ValidationError('A check box Consent cannot be created for the Add journey type.')

        return cleaned_data

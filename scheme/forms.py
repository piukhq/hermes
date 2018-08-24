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

        # Read-only fields (slug) are not validated on update so does not go through unique_together checks.
        if self.instance.id and self.instance.journey != cleaned_data['journey']:
            slug = self.instance.slug
            scheme = cleaned_data['scheme']
            journey = cleaned_data['journey']

            objects = Consent.objects.filter(slug=slug, scheme=scheme, journey=journey)

            if len(objects) > 0:
                raise ValidationError('Consent with this Slug, Scheme and Journey already exists.')

        return cleaned_data

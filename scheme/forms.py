from django import forms
from django.core.exceptions import ValidationError
from django.forms import ModelForm

from scheme.models import Scheme, Consent, JourneyTypes, validate_hex_colour, slug_regex


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


class SchemeForm(ModelForm):
    secondary_colour = forms.CharField(validators=[validate_hex_colour], required=False,
                                       help_text='Hex string e.g "#112233"')

    class Meta:
        model = Scheme
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def clean_point_name(self):
        point_name = self.cleaned_data['point_name']
        points_value_length = self.cleaned_data['max_points_value_length']

        if len(point_name) + points_value_length + 1 > Scheme.MAX_POINTS_VALUE_LENGTH:
            raise ValidationError('The length of the point name added to the maximum points value length must not '
                                  'exceed {}'.format(Scheme.MAX_POINTS_VALUE_LENGTH - 1))

        return point_name

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if slug_regex.match(slug):
            return slug
        else:
            raise ValidationError('Slug can only contain lowercase letters, hyphens and numbers')
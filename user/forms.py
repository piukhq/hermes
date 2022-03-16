from django.db.models import FileField
from django.forms import forms
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _


class MagicLinkTemplateFileField(FileField):
    """
    Same as FileField, but you can specify:
        * content_types - list containing allowed content_types. Example: ['application/pdf', 'image/jpeg']
        * max_upload_size - a number indicating the maximum file size allowed for upload.
            2.5MB - 2621440
            5MB - 5242880
            10MB - 10485760
            20MB - 20971520
            50MB - 5242880
            100MB 104857600
            250MB - 214958080
            500MB - 429916160
    """

    class FileSize(str):
        SUFFIXES = ["KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

        def byte_size(self):
            try:
                exp = self.SUFFIXES.index(self.__str__()[-2:].upper())
                return int(float(self.__str__()[:-2]) * 1024 ** (exp + 1))
            except ValueError:
                return self

    def __init__(self, *args, content_types=None, max_upload_size=None, **kwargs):
        self.content_types = content_types
        self.max_upload_size = self.FileSize(max_upload_size).byte_size()

        super().__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super().clean(*args, **kwargs)

        file = data.file
        try:
            content_type = file.content_type
            if content_type in self.content_types:
                if file.size > self.max_upload_size:
                    raise forms.ValidationError(
                        _(
                            f"Please keep filesize under {filesizeformat(self.max_upload_size)}. "
                            f"Current filesize {filesizeformat(file.size)}"
                        )
                    )
            else:
                raise forms.ValidationError(_("Filetype not supported."))
        except AttributeError:
            pass

        required_tag = "{{ magic_link_url }}"
        if required_tag not in str(data.read()):
            raise forms.ValidationError(_(f"Missing required tag in template: {required_tag}"))

        return data

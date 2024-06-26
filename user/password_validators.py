from django.core.exceptions import ValidationError


class NumericValidator:
    def validate(self, password, user=None):
        if not (any(character.isdigit() for character in password)):
            raise ValidationError(
                "This password is invalid. It must contain a numeric character.",
                code="password_has_no_numeric_character",
            )

    def get_help_text(self):
        return "Your password must contain at least one numeric character."


class UpperCaseCharacterValidator:
    def validate(self, password, user=None):
        if not (any(character.isupper() for character in password)):
            raise ValidationError(
                "This password is invalid. It must contain an upper case character.",
                code="password_has_no_upper_case_character",
            )

    def get_help_text(self):
        return "Your password must contain an upper case character."


class LowerCaseCharacterValidator:
    def validate(self, password, user=None):
        if not (any(character.islower() for character in password)):
            raise ValidationError(
                "This password is invalid. It must contain a lower case character.",
                code="password_has_no_lower_case_character",
            )

    def get_help_text(self):
        return "Your password must contain a lower case character."

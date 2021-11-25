# Generated by Django 2.2.24 on 2021-10-22 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheme", "0096_schemeoverrideerror"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schemeaccount",
            name="status",
            field=models.IntegerField(
                choices=[
                    (0, "Pending"),
                    (1, "Active"),
                    (403, "Invalid credentials"),
                    (432, "Invalid mfa"),
                    (530, "End site down"),
                    (531, "IP blocked"),
                    (532, "Tripped captcha"),
                    (5, "Please check your scheme account login details."),
                    (434, "Account locked on end site"),
                    (429, "Cannot connect, too many retries"),
                    (503, "Too many balance requests running"),
                    (520, "An unknown error has occurred"),
                    (9, "Midas unavailable"),
                    (10, "Wallet only card"),
                    (404, "Agent does not exist on midas"),
                    (533, "Password expired"),
                    (900, "Join"),
                    (444, "No user currently found"),
                    (536, "Error with the configuration or it was not possible to retrieve"),
                    (535, "Request was not sent"),
                    (445, "Account already exists"),
                    (537, "Service connection error"),
                    (401, "Failed validation"),
                    (406, "Pre-registered card"),
                    (446, "Update failed. Delete and re-add card."),
                    (204, "Pending manual check."),
                    (436, "Invalid card_number"),
                    (437, "You can only Link one card per day."),
                    (438, "Unknown Card number"),
                    (439, "General Error such as incorrect user details"),
                    (441, "Join in progress"),
                    (538, "A system error occurred during join"),
                    (447, "The scheme has requested this account should be deleted"),
                    (442, "Asynchronous join in progress"),
                    (443, "Asynchronous registration in progress"),
                    (901, "Enrol Failed"),
                    (902, "Ghost Card Registration Failed"),
                ],
                default=0,
            ),
        ),
        migrations.AlterField(
            model_name="schemeoverrideerror",
            name="error_code",
            field=models.IntegerField(
                choices=[
                    (0, "PENDING"),
                    (1, "ACTIVE"),
                    (403, "INVALID_CREDENTIALS"),
                    (432, "INVALID_MFA"),
                    (530, "END_SITE_DOWN"),
                    (531, "IP_BLOCKED"),
                    (532, "TRIPPED_CAPTCHA"),
                    (5, "INCOMPLETE"),
                    (434, "LOCKED_BY_ENDSITE"),
                    (429, "RETRY_LIMIT_REACHED"),
                    (503, "RESOURCE_LIMIT_REACHED"),
                    (520, "UNKNOWN_ERROR"),
                    (9, "MIDAS_UNREACHABLE"),
                    (10, "WALLET_ONLY"),
                    (404, "AGENT_NOT_FOUND"),
                    (533, "PASSWORD_EXPIRED"),
                    (900, "JOIN"),
                    (444, "NO_SUCH_RECORD"),
                    (536, "CONFIGURATION_ERROR"),
                    (535, "NOT_SENT"),
                    (445, "ACCOUNT_ALREADY_EXISTS"),
                    (537, "SERVICE_CONNECTION_ERROR"),
                    (401, "VALIDATION_ERROR"),
                    (406, "PRE_REGISTERED_CARD"),
                    (446, "FAILED_UPDATE"),
                    (204, "PENDING_MANUAL_CHECK"),
                    (436, "CARD_NUMBER_ERROR"),
                    (437, "LINK_LIMIT_EXCEEDED"),
                    (438, "CARD_NOT_REGISTERED"),
                    (439, "GENERAL_ERROR"),
                    (441, "JOIN_IN_PROGRESS"),
                    (538, "JOIN_ERROR"),
                    (447, "SCHEME_REQUESTED_DELETE"),
                    (442, "JOIN_ASYNC_IN_PROGRESS"),
                    (443, "REGISTRATION_ASYNC_IN_PROGRESS"),
                    (901, "ENROL_FAILED"),
                    (902, "REGISTRATION_FAILED"),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="schemeoverrideerror",
            name="error_slug",
            field=models.CharField(
                choices=[
                    ("PENDING", "PENDING"),
                    ("ACTIVE", "ACTIVE"),
                    ("INVALID_CREDENTIALS", "INVALID_CREDENTIALS"),
                    ("INVALID_MFA", "INVALID_MFA"),
                    ("END_SITE_DOWN", "END_SITE_DOWN"),
                    ("IP_BLOCKED", "IP_BLOCKED"),
                    ("TRIPPED_CAPTCHA", "TRIPPED_CAPTCHA"),
                    ("INCOMPLETE", "INCOMPLETE"),
                    ("LOCKED_BY_ENDSITE", "LOCKED_BY_ENDSITE"),
                    ("RETRY_LIMIT_REACHED", "RETRY_LIMIT_REACHED"),
                    ("RESOURCE_LIMIT_REACHED", "RESOURCE_LIMIT_REACHED"),
                    ("UNKNOWN_ERROR", "UNKNOWN_ERROR"),
                    ("MIDAS_UNREACHABLE", "MIDAS_UNREACHABLE"),
                    ("WALLET_ONLY", "WALLET_ONLY"),
                    ("AGENT_NOT_FOUND", "AGENT_NOT_FOUND"),
                    ("PASSWORD_EXPIRED", "PASSWORD_EXPIRED"),
                    ("JOIN", "JOIN"),
                    ("NO_SUCH_RECORD", "NO_SUCH_RECORD"),
                    ("CONFIGURATION_ERROR", "CONFIGURATION_ERROR"),
                    ("NOT_SENT", "NOT_SENT"),
                    ("ACCOUNT_ALREADY_EXISTS", "ACCOUNT_ALREADY_EXISTS"),
                    ("SERVICE_CONNECTION_ERROR", "SERVICE_CONNECTION_ERROR"),
                    ("VALIDATION_ERROR", "VALIDATION_ERROR"),
                    ("PRE_REGISTERED_CARD", "PRE_REGISTERED_CARD"),
                    ("FAILED_UPDATE", "FAILED_UPDATE"),
                    ("PENDING_MANUAL_CHECK", "PENDING_MANUAL_CHECK"),
                    ("CARD_NUMBER_ERROR", "CARD_NUMBER_ERROR"),
                    ("LINK_LIMIT_EXCEEDED", "LINK_LIMIT_EXCEEDED"),
                    ("CARD_NOT_REGISTERED", "CARD_NOT_REGISTERED"),
                    ("GENERAL_ERROR", "GENERAL_ERROR"),
                    ("JOIN_IN_PROGRESS", "JOIN_IN_PROGRESS"),
                    ("JOIN_ERROR", "JOIN_ERROR"),
                    ("SCHEME_REQUESTED_DELETE", "SCHEME_REQUESTED_DELETE"),
                    ("JOIN_ASYNC_IN_PROGRESS", "JOIN_ASYNC_IN_PROGRESS"),
                    ("REGISTRATION_ASYNC_IN_PROGRESS", "REGISTRATION_ASYNC_IN_PROGRESS"),
                    ("ENROL_FAILED", "ENROL_FAILED"),
                    ("REGISTRATION_FAILED", "REGISTRATION_FAILED"),
                ],
                max_length=50,
            ),
        ),
    ]

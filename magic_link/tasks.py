from azure.storage.blob import BlockBlobService
from celery import shared_task

from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives


def get_email_template():
    blob_client = BlockBlobService(connection_string=settings.AZURE_CONNECTION_STRING)
    template = blob_client.get_blob_to_text(
        settings.AZURE_CONTAINER,
        settings.MAGIC_LINK_TEMPLATE
    )

    return template.content


def send_mail(subject, message, from_email, recipient_list, reply_to,
              fail_silently=False, auth_user=None, auth_password=None,
              connection=None, html_message=None):
    """Copy of existing django.core.mail function "send_mail" but also accepts a reply_to parameter"""

    connection = connection or get_connection(
        username=auth_user,
        password=auth_password,
        fail_silently=fail_silently,
    )
    mail = EmailMultiAlternatives(subject, message, from_email, recipient_list,
                                  reply_to=reply_to, connection=connection)
    if html_message:
        mail.attach_alternative(html_message, 'text/html')

    return mail.send()


@shared_task
def send_magic_link(email, email_from, subject, token, url, external_name, expiry_date):
    template = get_email_template()
    message = template.format(url=url, token=token, expiry=expiry_date, external_name=external_name)
    send_mail(
        subject=subject,
        message=message,
        html_message=message,
        from_email=email_from or settings.DEFAULT_MAGIC_LINK_FROM_EMAIL.format(external_name=external_name),
        reply_to=["no-reply@bink.com"],
        recipient_list=[email],
        fail_silently=False
    )

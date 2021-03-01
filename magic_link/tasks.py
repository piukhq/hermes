from azure.storage.blob import BlockBlobService
from celery import shared_task

from django.conf import settings
from django.core.mail import send_mail


def get_email_template():
    blob_client = BlockBlobService(connection_string=settings.AZURE_CONNECTION_STRING)
    template = blob_client.get_blob_to_text(
        settings.AZURE_CONTAINER,
        settings.MAGIC_LINK_TEMPLATE
    )

    return template.content


@shared_task
def send_magic_link(email, expiry, token, url, bundle_id):
    template = get_email_template()
    send_mail(
        'Magic Link Request',
        template.format(url=url, token=token, expiry=expiry),
        settings.MAGIC_LINK_FROM_EMAIL.format(channel=bundle_id),
        [email],
        fail_silently=False
    )

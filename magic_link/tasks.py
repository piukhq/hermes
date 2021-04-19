from azure.storage.blob import BlockBlobService
from celery import shared_task
from scheme.models import Scheme, SchemeBundleAssociation, SchemeImage
from user.models import ClientApplicationBundle
from common.models import Image

from django.conf import settings
from django.core.mail import send_mail


def get_email_template():
    blob_client = BlockBlobService(connection_string=settings.AZURE_CONNECTION_STRING)
    template = blob_client.get_blob_to_text(
        settings.AZURE_CONTAINER,
        settings.MAGIC_LINK_TEMPLATE
    )

    return template.content


def populate_template_with_data(bundle_id, template, token):

    bundle = ClientApplicationBundle.objects.get(id=bundle_id)
    plan = Scheme.objects.filter(related_bundle=bundle).get()
    plan_name = plan.plan_name
    plan_summary = plan.plan_summary
    plan_description = plan.description
    magic_link_url = bundle.magic_link_url + token
    hero_image = SchemeImage.objects.get(scheme=plan, image_type_code=Image.HERO).image
    alt_hero_image = SchemeImage.objects.get(scheme=plan, image_type_code=Image.ALT_HERO).image

    replacement_fields = {
        '{{magic-link-url}}': magic_link_url,
        '{{plan-name}}': plan_name,
        '{{plan-description}}': plan_description,
        '{{plan-summary}}': plan_summary,
        '{{hero-image}}': hero_image,
        '{{alt-hero-image}}': alt_hero_image
    }

    for key, value in replacement_fields.items():
        template = template.replace(key, value)

    return template


@shared_task
def send_magic_link(email, token, url, external_name, expiry_date, bundle_id):
    template = get_email_template()
    populated_template = populate_template_with_data(bundle_id, template, token)
    send_mail(
        'Magic Link Request',
        populated_template.format(url=url, token=token, expiry=expiry_date, external_name=external_name),
        settings.MAGIC_LINK_FROM_EMAIL.format(external_name=external_name),
        [email],
        fail_silently=False
    )

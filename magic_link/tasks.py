import logging

from celery import shared_task

from django.template import Template, Context
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives

from scheme.models import Scheme, SchemeImage, Image, SchemeBundleAssociation
from user.models import ClientApplicationBundle


logger = logging.getLogger(__name__)


def get_email_template(bundle_id: str, slug: str) -> [str, ClientApplicationBundle]:
    try:
        bundle = ClientApplicationBundle.objects.get(bundle_id=bundle_id, scheme__slug=slug,
                                                     schemebundleassociation__status=SchemeBundleAssociation.ACTIVE)
        return bundle.template.read().decode(), bundle

    except ClientApplicationBundle.DoesNotExist:
        logger.exception(f"{ClientApplicationBundle.__name__} not found when retrieving magic link template")


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
def send_magic_link(email, email_from, subject, token, external_name, slug, bundle_id):

    template, bundle = get_email_template(bundle_id, slug)

    email_content = populate_template(
        bundle=bundle,
        token=token,
        slug=slug,
        unpopulated_template=template
    )

    send_mail(
        subject=subject,
        message=email_content,
        html_message=email_content,
        from_email=email_from or settings.DEFAULT_MAGIC_LINK_FROM_EMAIL.format(external_name=external_name),
        reply_to=["no-reply@bink.com"],
        recipient_list=[email],
        fail_silently=False
    )


def populate_template(bundle, token, slug, unpopulated_template):

    template = Template(unpopulated_template)

    plan = Scheme.objects.get(slug=slug)
    plan_name = plan.plan_name
    plan_summary = plan.plan_summary
    plan_description = plan.plan_description
    magic_link_url = bundle.magic_link_url+token
    hero_image = SchemeImage.objects.get(scheme=plan, image_type_code=Image.HERO).image
    alt_hero_image = SchemeImage.objects.get(scheme=plan, image_type_code=Image.ALT_HERO).image

    context = Context({
                    'magic_link_url': magic_link_url,
                    'plan_name': plan_name,
                    'plan_description': plan_description,
                    'plan_summary': plan_summary,
                    'hero_image': hero_image,
                    'alt_hero_image': alt_hero_image,
    })

    email_content = template.render(context)

    return email_content

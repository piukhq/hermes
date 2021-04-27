import logging

from celery import shared_task

from django.template import Template, Context
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives

from scheme.models import Scheme, SchemeImage, Image
from user.utils import MagicLinkData

logger = logging.getLogger(__name__)


def populate_template(magic_link_data: MagicLinkData) -> str:

    template = Template(magic_link_data.template)

    plan = Scheme.objects.get(slug=magic_link_data.slug)
    # Token is appended for now as url ends in a querystring e.g /?magic-link=
    # This should be changed in the form of string substitution if we need to modify the url further
    magic_link_url = f"{magic_link_data.url}{magic_link_data.token}"
    hero_image = SchemeImage.objects.get(scheme=plan, image_type_code=Image.HERO).image
    alt_hero_image = SchemeImage.objects.get(scheme=plan, image_type_code=Image.ALT_HERO).image

    context = Context({
        'magic_link_url': magic_link_url,
        'plan_name': plan.plan_name,
        'plan_description': plan.plan_description,
        'plan_summary': plan.plan_summary,
        'hero_image': hero_image.url,
        'alt_hero_image': alt_hero_image.url,
    })

    email_content = template.render(context)

    return email_content


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
def send_magic_link(magic_link_data: MagicLinkData):
    email_content = populate_template(magic_link_data=magic_link_data)
    send_mail(
        subject=magic_link_data.subject,
        message=email_content,
        html_message=email_content,
        from_email=magic_link_data.email_from or settings.DEFAULT_MAGIC_LINK_FROM_EMAIL.format(
            external_name=magic_link_data.external_name
        ),
        reply_to=["no-reply@bink.com"],
        recipient_list=[magic_link_data.email],
        fail_silently=False
    )

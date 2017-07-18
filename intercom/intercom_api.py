import datetime
import json
import requests
import time

from django.conf import settings

SETTING_CUSTOM_ATTRIBUTES = ['marketing-bink', 'marketing-external']
ISSUED_JOIN_CARD_EVENT = 'issued-join-card'


class IntercomException(Exception):
    pass


def post_issued_join_card_event(token, user_id, company_name, slug):
    """
    Submit an event to the Intercom service
    :param token: Intercom API access token
    :param user_id: uuid identifier for the user (user.uid from CustomUser models)
    :param company_name: scheme company name
    :param slug: scheme slug
    :return: the whole response
    """
    headers = _get_headers(token)
    payload = {
        'user_id': user_id,
        'event_name': ISSUED_JOIN_CARD_EVENT,
        'created_at': int(time.time()),
        'metadata': {
            'company name': company_name,
            'slug': slug
        }
    }
    response = requests.post(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_EVENTS_PATH),
        headers=headers,
        data=json.dumps(payload)
    )

    if response.status_code != 202:
        raise IntercomException('Error post_issued_join_card_event: {}'.format(response.text))

    return response


def reset_user_settings(token, user_id):
    """
    Reset user custom attributes
    :param token: Intercom API access token
    :param user_id: uuid identifier for the user
    :return: the whole response
    """
    headers = _get_headers(token)

    payload = {
        'user_id': user_id,
        'custom_attributes': dict((attr_name, None) for attr_name in SETTING_CUSTOM_ATTRIBUTES)
    }
    response = requests.post(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_USERS_PATH),
        headers=headers,
        data=json.dumps(payload)
    )

    if response.status_code != 200:
        raise IntercomException('Error reset_user_custom_attributes: {}'.format(response.text))

    return response


def update_user_custom_attribute(token, user_id, attr_name, attr_value):
    """
    Update a user custom attribute
    :param token: Intercom API access token
    :param user_id: uuid identifier for the user
    :param attr_name: name of the attribute to be updated
    :param attr_value: new value of the attribute
    :return: the whole response
    """
    headers = _get_headers(token)

    payload = {
        'user_id': user_id,
        'custom_attributes': {
            attr_name: attr_value,
        }
    }

    response = requests.post(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_USERS_PATH),
        headers=headers,
        data=json.dumps(payload),
    )

    if response.status_code != 200:
        raise IntercomException('Error update_user_custom_attribute: {}'.format(response.text))

    return response


def update_account_status_custom_attribute(token, account):
    """
    Update scheme account user custom attribute with the format:
    'scheme-slug': '{status},YYYY/mm/dd'
    :param token: Intercom API access token
    :param user_id: uuid identifier for the user
    :param account: scheme account to be send to intercom
    :return: the whole response
    """
    attr_value = "{},{},{},{}".format(
        str(account.is_deleted).lower(),
        account.status_key,
        _get_today_datetime().strftime("%Y/%m/%d"),
        account.scheme.slug
    )
    return update_user_custom_attribute(token, account.user.uid, account.scheme.company, attr_value)


def update_payment_account_custom_attribute(token, account):
    """
    Update payment card account user custom attribute
    Data to transfer:
        [Status e.g. pending, active etc],
        [Payment Card Type e.g. Visa, Mastercard, AMEX],
        [Name on Card],
        [Expiry Month],
        [ExpiryYear],
        [Country],
        [PAN Start],
        [PAN End],
        [Created Date],
        [Last Update Date e.g. pending to Active],
        [is delete status]
    :param token: Intercom API access token
    :param account: payment card account to be send to intercom
    :return: the whole response
    """

    attr_value = "{},{},{},{},{},{},{},{},{},{},{}".format(
        "STS:{}".format(account.status_name),
        "CRD:{}".format(account.payment_card.system_name),
        "NAM:{}".format(account.name_on_card),
        "EXPM:{}".format(str(account.expiry_month)),
        "EXPY:{}".format(str(account.expiry_year)),
        "CTY:{}".format(account.country),
        "BIN:{}".format(account.pan_start),
        "END:{}".format(account.pan_end),
        "CTD:{}".format(account.created.strftime("%Y/%m/%d")),
        "UPD:{}".format(account.updated.strftime("%Y/%m/%d")),
        "DEL:{}".format(str(account.is_deleted).lower()),
    )

    key = "PAYMENT CARD {}".format(str(account.order))

    return update_user_custom_attribute(token, account.user.uid, key, attr_value)


def get_user_events(token, user_id):
    """ Retrieves the user identified with the user_id uuid"""
    headers = _get_headers(token)

    return requests.get(
        '{host}/{path}?type=user&user_id={user_id}'.format(
            host=settings.INTERCOM_HOST,
            path=settings.INTERCOM_EVENTS_PATH,
            user_id=user_id
        ),
        headers=headers
    )


def _get_today_datetime():
    return datetime.datetime.today()


def _get_headers(token):
    return {
        'Authorization': 'Bearer {0}'.format(token),
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

import json
import requests
import time

from django.conf import settings


USER_CUSTOM_ATTRIBUTES = ['marketing-bink', 'marketing-external']
ISSUED_JOIN_CARD_EVENT = 'issued-join-card'


class IntercomException(Exception):
    pass


def post_issued_join_card_event(token, user_id):
    """
    Submit an event to the Intercom service
    :param user_id: uuid identifier for the user
    :param event: name of the event that occurred
    :return: the whole response
    """
    headers = _get_headers(token)

    response = requests.post(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_EVENTS_PATH),
        headers=headers,
        data=json.dumps({
            'user_id': user_id,
            'event_name': ISSUED_JOIN_CARD_EVENT,
            'created_at': int(time.time())
        })
    )

    if response.status_code != 202:
        raise IntercomException('Error post_issued_join_card_event: {}'.format(response.text))

    return response


def reset_user_custom_attributes(token, user_id):
    """
    Reset user custom attributes
    :param user_id: uuid identifier for the user
    :return: the whole response
    """
    headers = _get_headers(token)

    payload = {
        'user_id': user_id,
        'custom_attributes': dict((attr_name, None) for attr_name in USER_CUSTOM_ATTRIBUTES)
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
        data=json.dumps(payload)
    )

    if response.status_code != 200:
        raise IntercomException('Error update_user_custom_attribute: {}'.format(response.text))

    return response


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


def _get_headers(token):
    return {
        'Authorization': 'Bearer {0}'.format(token),
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

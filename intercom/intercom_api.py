import json
import requests
import time

from django.conf import settings


def post_event(token, user_id, event):
    """
    Submit an event to the Intercom service
    :param user_id: uuid identifier for the user
    :param event: name of the event that occurred
    :return: the whole response
    """
    headers = _get_headers(token)

    return requests.post(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_EVENTS_PATH),
        headers=headers,
        data=json.dumps({
            'user_id': user_id,
            'event_name': event,
            'created_at': int(time.time())
        })
    )


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

    return requests.post(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_USERS_PATH),
        headers=headers,
        data=json.dumps(payload)
    )


def update_user_attributes(token, user_id, attr):
    """
    Update user attributes
    :param user_id: uuid identifier for the user
    :param attr: A hash of key/value pairs containing any all the attributes to be updated
    :return: the whole response
    """
    headers = _get_headers(token)

    payload = {
        'user_id': user_id,
    }
    payload.update(attr)

    return requests.post(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_USERS_PATH),
        headers=headers,
        data=json.dumps(payload)
    )


def get_users(token):
    """Retrieves all the user from the Intercom service"""
    headers = _get_headers(token)

    return requests.get(
        '{host}/{path}'.format(host=settings.INTERCOM_HOST, path=settings.INTERCOM_USERS_PATH),
        headers=headers
    )


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

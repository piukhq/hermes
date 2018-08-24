import datetime
import json
import time
import requests
from django.conf import settings

OLYMPUS_SERVICE_TRACKING_TYPE = 6  # Defined in Mnemosyne project
SETTING_CUSTOM_ATTRIBUTES = ['marketing-bink', 'marketing-external']


class PushError(Exception):
    pass
# Public Methods


def post_event(user, event_name, metadata=None, to_intercom=False):
    event = {
        'time': _current_unix_timestamp(),
        'type': OLYMPUS_SERVICE_TRACKING_TYPE,
        'id': event_name,
        'intercom': to_intercom,
    }

    if metadata:
        event['data'] = metadata

    _send_to_mnemosyne(
        user=user,
        event=event
    )


def reset_user_settings(user):
    update_attributes(user, dict((attr_name, None) for attr_name in SETTING_CUSTOM_ATTRIBUTES))


def update_scheme_account_attribute(account):
    update_attribute(account.user, account.scheme.company, "{},{},{},{}".format(
        str(account.is_deleted).lower(),
        account.status_key,
        _get_today_datetime().strftime("%Y/%m/%d"),
        account.scheme.slug
    ))


def update_attribute(user, key, value):
    update_attributes(user, {
        key: value
    })


def update_attributes(user, attributes):
    _send_to_mnemosyne(user, attributes=attributes)


# Private Methods

def _send_to_mnemosyne(user, event=None, attributes=None):

    if not settings.MNEMOSYNE_URL:
        raise PushError  # Defaults to None for now, but we cannot miss events

    payload = {
        'service': 'hermes',
        'user': {
            'e': user.email,
            'id': user.uid
        }
    }

    if event:
        payload['events'] = [event]

    if attributes:
        payload['attributes'] = attributes

    destination = '{}/analytics/service'.format(settings.MNEMOSYNE_URL)
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY)
    }
    body_data = json.dumps(payload)

    try:
        response = requests.post(destination, data=body_data, headers=headers)
    except Exception as ex:
        raise PushError from ex

    try:
        response.raise_for_status()
    except Exception as ex:
        raise PushError from ex


def _current_unix_timestamp():
    return int(time.time())


def _get_today_datetime():
    return datetime.datetime.today()

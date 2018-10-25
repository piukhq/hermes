import datetime
import json
import time
import requests
from django.conf import settings
from raven.contrib.django.raven_compat.models import client as sentry
from scheme.models import SchemeAccount


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

    try:
        _send_to_mnemosyne(
            user=user,
            event=event
        )
    except PushError:
        sentry.captureException()
        pass


def reset_user_settings(user):
    update_attributes(user, dict((attr_name, None) for attr_name in SETTING_CUSTOM_ATTRIBUTES))


def get_status(status):
    if status is not None:
        for stat in SchemeAccount.STATUSES:
            if stat[0] == status:
                return stat[1]
    return status


def update_scheme_account_attribute_new_status(account, new_status):
    current_status = get_status(new_status)

    attributes = {
        account.scheme.company: "{},{},{},{},prev_{},current_{}".format(
            str(account.is_deleted).lower(),
            current_status,
            _get_today_datetime().strftime("%Y/%m/%d"),
            account.scheme.slug,
            account.status_key,
            current_status
        )}

    update_attributes(account.user, attributes)


def update_scheme_account_attribute(account, old_status=None):
    previous_status = get_status(old_status)

    attributes = {
        account.scheme.company: "{},{},{},{},prev_{},current_{}".format(
            str(account.is_deleted).lower(),
            account.status_key,
            _get_today_datetime().strftime("%Y/%m/%d"),
            account.scheme.slug,
            previous_status,
            account.status_key
        )}

    update_attributes(account.user, attributes)


def update_attributes(user, attributes):
    try:
        _send_to_mnemosyne(user, attributes=attributes)
    except PushError:
        sentry.captureException()
        pass


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

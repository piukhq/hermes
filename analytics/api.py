import datetime
import json
import time

import requests
import sentry_sdk
from django.conf import settings

OLYMPUS_SERVICE_TRACKING_TYPE = 6  # Defined in Mnemosyne project
SETTING_CUSTOM_ATTRIBUTES = ["marketing-bink", "marketing-external"]


class PushError(Exception):
    pass


# Public Methods


def post_event(user, event_name, metadata=None, to_intercom=False):
    event = {
        "time": _current_unix_timestamp(),
        "type": str(OLYMPUS_SERVICE_TRACKING_TYPE),
        "id": event_name,
        "intercom": to_intercom,
    }

    if metadata:
        event["data"] = metadata

    try:
        _send_to_mnemosyne(user=user, event=event)
    except PushError:
        sentry_sdk.capture_exception()
        pass


def reset_user_settings(user):
    update_attributes(user, dict((attr_name, None) for attr_name in SETTING_CUSTOM_ATTRIBUTES))


def update_scheme_account_attribute_new_status(scheme_account_entry, new_status):

    attributes = {
        scheme_account_entry.scheme_account.scheme.company: "{},{},{},{},prev_{},current_{}".format(
            str(scheme_account_entry.account.is_deleted).lower(),
            new_status,
            _get_today_datetime().strftime("%Y/%m/%d"),
            scheme_account_entry.scheme_account.scheme.slug,
            scheme_account_entry.status_key,
            new_status,
        )
    }

    update_attributes(scheme_account_entry.user, attributes)


def update_scheme_account_attribute(scheme_account_entry, old_status=None):

    attributes = {
        scheme_account_entry.scheme_account.scheme.company: "{},{},{},{},prev_{},current_{}".format(
            str(scheme_account_entry.scheme_account.is_deleted).lower(),
            scheme_account_entry.status_key,
            _get_today_datetime().strftime("%Y/%m/%d"),
            scheme_account_entry.scheme_account.scheme.slug,
            old_status,
            scheme_account_entry.status_key,
        )
    }

    update_attributes(scheme_account_entry.user, attributes)


def update_attributes(user, attributes):
    try:
        _send_to_mnemosyne(user, attributes=attributes)
    except PushError:
        sentry_sdk.capture_exception()
        pass


# Private Methods


def _send_to_mnemosyne(user, event=None, attributes=None):

    if not settings.MNEMOSYNE_URL:
        # assume we are not using mnemosine and avoid sending data
        return None

    payload = {"service": "hermes", "user": {"e": user.email, "id": user.uid}}

    if event:
        payload["events"] = [event]

    if attributes:
        payload["attributes"] = attributes

    destination = "{}/analytics/service".format(settings.MNEMOSYNE_URL)
    headers = {"content-type": "application/json", "Authorization": "Token {}".format(settings.SERVICE_API_KEY)}
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

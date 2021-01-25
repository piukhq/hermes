from collections import namedtuple
from typing import Optional, Type, TYPE_CHECKING, Tuple
from unittest.mock import patch

from django.contrib import admin
from django.utils import timezone
from rest_framework.test import APITestCase

from history.enums import HistoryModel, DeleteField
from history.models import HistoricalBase
from history.serializers import get_body_serializer
from history.signals import HISTORY_CONTEXT, EXCLUDED_FIELDS, get_user_and_channel
from history.tasks import bulk_record_history

if TYPE_CHECKING:
    from django.db.models import Model

user_info = namedtuple("user_info", ("user_id", "channel"))


class HistoryAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if change:
            update_fields = []
            for key, value in form.cleaned_data.items():
                # True if something changed in model
                if value != form.initial[key]:
                    update_fields.append(key)

            obj.save(update_fields=update_fields)
        else:
            obj.save()


class GlobalMockAPITestCase(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.history_patcher = patch("history.signals.record_history", autospec=True)
        cls.bulk_history_patcher = patch("history.utils.bulk_record_history", autospec=True)
        cls.history_patcher.start()
        cls.bulk_history_patcher.start()
        super(GlobalMockAPITestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.history_patcher.stop()
        cls.bulk_history_patcher.stop()
        super().tearDownClass()


def set_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k, v in kwargs.items():
            setattr(HISTORY_CONTEXT, k, v)


def clean_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k in kwargs:
            if hasattr(HISTORY_CONTEXT, k):
                delattr(HISTORY_CONTEXT, k)


def _get_change_type_and_details(update_fields: list, is_deleted: Tuple[str, bool]) -> Tuple[Optional[str], str]:
    change_details = ""
    deleted_key, deleted_value = is_deleted
    if update_fields:
        if set(update_fields) <= EXCLUDED_FIELDS:
            return None, change_details
        else:
            update_fields = set(update_fields) - EXCLUDED_FIELDS

    else:
        update_fields = set()

    if deleted_key in update_fields and deleted_value:
        change_type = HistoricalBase.DELETE

    else:
        change_type = HistoricalBase.UPDATE
        change_details = ", ".join(update_fields)

    return change_type, change_details


def history_bulk_update(
        model: Type["Model"],
        objs: list,
        update_fields: list = None,
        batch_size: int = None,
) -> None:

    created_at = timezone.now()
    model_name = model.__name__

    model.objects.bulk_update(objs, update_fields, batch_size=batch_size)

    if hasattr(model, DeleteField.IS_DELETED.value):
        is_deleted = DeleteField.IS_DELETED.get_value(objs)
    elif hasattr(model, DeleteField.IS_ACTIVE.value):
        is_deleted = DeleteField.IS_ACTIVE.get_value(objs)
    else:
        is_deleted = DeleteField.NONE.get_value()

    change_type, change_details = _get_change_type_and_details(update_fields, is_deleted)
    user_id, channel = get_user_and_channel()
    history_objs = []
    extra_bodies = None
    extra_journey = None

    if model_name in [HistoryModel.PAYMENT_CARD_ACCOUNT, HistoryModel.SCHEME_ACCOUNT, HistoryModel.CUSTOM_USER]:
        extra_bodies = get_body_serializer(model_name)(objs, many=True).data

        if model_name == HistoryModel.SCHEME_ACCOUNT and hasattr(HISTORY_CONTEXT, "journey"):
            extra_journey = HISTORY_CONTEXT.journey
            del HISTORY_CONTEXT.journey

    for i, instance in enumerate(objs):
        extra = {"user_id": user_id, "channel": channel}

        if extra_bodies is not None:
            extra["body"] = extra_bodies[i]

        if extra_journey is not None:
            extra["journey"] = extra_journey

        if hasattr(instance, "payment_card_account_id"):
            extra["payment_card_account_id"] = instance.payment_card_account_id

        if hasattr(instance, "scheme_account_id"):
            extra["scheme_account_id"] = instance.scheme_account_id

        if hasattr(instance, "email"):
            extra["email"] = instance.email

        if hasattr(instance, "external_id"):
            extra["external_id"] = instance.external_id

        history_objs.append({
            "created": created_at,
            "change_type": change_type,
            "change_details": change_details,
            "instance_id": instance.id,
            **extra
        })

    bulk_record_history.delay(model_name, history_objs)

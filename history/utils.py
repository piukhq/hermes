import re
from collections import namedtuple
from typing import Optional, Type, TYPE_CHECKING, Tuple, Iterable
from unittest.mock import patch

from django.contrib import admin
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APITestCase

from history.apps import logger
from history.enums import DeleteField
from history.models import HistoricalBase, get_required_extra_fields
from history.serializers import get_body_serializer
from history.signals import HISTORY_CONTEXT, EXCLUDED_FIELDS, get_user_and_channel
from history.tasks import bulk_record_history

if TYPE_CHECKING:
    from django.db.models import Model
    from datetime import datetime

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


def _bulk_create_with_id(model: Type["Model"], objs: Iterable, batch_size: int) -> list:
    """
    not suited for large bulks of objects until we implement batch logic
    """

    if not hasattr(objs, "__delitem__"):
        objs = list(objs)

    created_objs = []
    while objs:
        try:
            created_objs = model.objects.bulk_create(objs, batch_size=batch_size)
            objs = []
        except IntegrityError as e:
            """
            IntegrityError example:
            "duplicate key value violates unique constraint
            "ubiquity_paymentcardsche_payment_card_account_id__c41ba7ab_uniq"\n
            DETAIL:  Key (payment_card_account_id, scheme_account_id)=(36536, 239065) already exists."
            """
            parsed = re.search(r"\((?P<keys>.*)\)=\((?P<values>.*)\)", str(e))
            found_items = parsed.groupdict()
            if not found_items:
                raise e

            parsed_dict = {k: v.split(", ") for k, v in found_items.items()}
            existing_entry_dict = dict(zip(parsed_dict["keys"], parsed_dict["values"]))

            logger.warning(
                f"{model.__name__} bulk create hit an IntegrityError, starting recovery procedure.\n"
                f"Error caused by: {existing_entry_dict}"
            )

            for i, obj in enumerate(objs):
                if all(map(lambda k: str(getattr(obj, k)) == existing_entry_dict[k], existing_entry_dict)):
                    del objs[i]

    return created_objs


def _format_history_objs(
        model_name: str, created_at: "datetime", objs: Iterable, change_type: str, change_details: str
) -> list:
    user_id, channel = get_user_and_channel()
    required_extra_fields = get_required_extra_fields(model_name)
    history_objs = []
    extra_bodies = None
    extra_journey = None

    if "body" in required_extra_fields:
        extra_bodies = get_body_serializer(model_name)(objs, many=True).data

    if "journey" in required_extra_fields and hasattr(HISTORY_CONTEXT, "journey"):
        extra_journey = HISTORY_CONTEXT.journey
        del HISTORY_CONTEXT.journey

    for i, instance in enumerate(objs):
        extra = {"user_id": user_id, "channel": channel}

        if extra_bodies is not None:
            extra["body"] = extra_bodies[i]

        if extra_journey is not None:
            extra["journey"] = extra_journey

        for field in required_extra_fields:
            if field not in extra and hasattr(instance, field):
                extra[field] = getattr(instance, field)

        history_objs.append(
            {
                "created": created_at,
                "change_type": change_type,
                "change_details": change_details,
                "instance_id": instance.id,
                **extra,
            }
        )

    return history_objs


def _history_bulk(
        model: Type["Model"],
        objs: Iterable,
        update_fields: list = None,
        *,
        batch_size: int = None,
        ignore_conflicts: bool = False,
        update: bool = False,
) -> list:
    created_at = timezone.now()
    model_name = model.__name__

    if update:
        model.objects.bulk_update(objs, update_fields, batch_size=batch_size)

        if hasattr(model, DeleteField.IS_DELETED.value):
            is_deleted = DeleteField.IS_DELETED.get_value(objs)
        elif hasattr(model, DeleteField.IS_ACTIVE.value):
            is_deleted = DeleteField.IS_ACTIVE.get_value(objs)
        else:
            is_deleted = DeleteField.NONE.get_value()

        change_type, change_details = _get_change_type_and_details(update_fields, is_deleted)
    else:

        if ignore_conflicts:
            objs = _bulk_create_with_id(model, objs, batch_size)
        else:
            objs = model.objects.bulk_create(objs, batch_size=batch_size)

        change_type, change_details = HistoricalBase.CREATE, ""

    history_objs = _format_history_objs(
        model_name,
        created_at,
        objs,
        change_type,
        change_details
    )

    bulk_record_history.delay(model_name, history_objs)
    return objs


def history_bulk_update(
        model: Type["Model"], objs: Iterable, update_fields: list = None, batch_size: int = None
) -> None:
    _history_bulk(model, objs, update_fields, batch_size=batch_size, update=True)


def history_bulk_create(
        model: Type["Model"], objs: Iterable, batch_size: int = None, ignore_conflicts: bool = False
) -> list:
    return _history_bulk(model, objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts, update=False)

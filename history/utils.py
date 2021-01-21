from collections import namedtuple
from typing import Optional
from unittest.mock import patch

from django.contrib import admin
from rest_framework.test import APITestCase

from history.signals import HISTORY_CONTEXT

user_info = namedtuple("user_info", ("user_id", "channel"))


def set_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k, v in kwargs.items():
            setattr(HISTORY_CONTEXT, k, v)


def clean_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k in kwargs:
            if hasattr(HISTORY_CONTEXT, k):
                delattr(HISTORY_CONTEXT, k)


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
        cls.history_patcher.start()
        super(GlobalMockAPITestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.history_patcher.stop()
        super().tearDownClass()

from typing import Optional

from history.signals import HISTORY_CONTEXT


def set_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k, v in kwargs.items():
            setattr(HISTORY_CONTEXT, k, v)


def clean_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k in kwargs:
            if hasattr(HISTORY_CONTEXT, k):
                delattr(HISTORY_CONTEXT, k)

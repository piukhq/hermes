from typing import Optional

from history.signals import LOCAL_CONTEXT


def set_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k, v in kwargs.items():
            setattr(LOCAL_CONTEXT, k, v)


def clean_history_kwargs(kwargs: Optional[dict]) -> None:
    if kwargs:
        for k in kwargs:
            if hasattr(LOCAL_CONTEXT, k):
                delattr(LOCAL_CONTEXT, k)

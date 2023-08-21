from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings

from api_messaging.message_broker import SendingService


@pytest.mark.parametrize(
    ("pub_side_effect", "expected_retry_n"),
    [
        pytest.param(
            lambda *_: None,
            0,
            id="Test success with no retries",
        ),
        pytest.param(
            ValueError("sample connection error"),
            -1,
            id="Test max retries exceeded",
        ),
    ]
    + [
        pytest.param(
            [ValueError("sample connection error")] * i + [lambda *_: None],
            i,
            id=f"Test success after {i} retry.",
        )
        for i in range(1, settings.PUBLISH_MAX_RETRIES + 1)
    ],
)
def test__pub_retry(pub_side_effect: Callable | list[Callable], expected_retry_n: int) -> None:
    mock_logger = MagicMock()

    def mock_init(self: SendingService, *_: str) -> None:
        self._conn = None
        self.producer = {}
        self.queue = {}
        self.exchange = {}
        self.logger = mock_logger

    with (
        patch.object(SendingService, "__init__", mock_init),
        patch.object(SendingService, "connect") as mock_connect,
        patch.object(SendingService, "close") as mock_close,
        patch.object(SendingService, "_pub") as mock_pub,
        patch("api_messaging.message_broker.sleep") as mock_sleep,
    ):
        mock_pub.side_effect = pub_side_effect

        service = SendingService("")
        raised_exc: Exception | None = None

        try:
            service.send({}, {}, "test-queue")
        except Exception as e:
            raised_exc = e

        match expected_retry_n:
            case 0:
                mock_connect.assert_not_called()
                mock_close.assert_not_called()
                mock_logger.warning.assert_not_called()
                mock_logger.exception.assert_not_called()
                mock_sleep.assert_not_called()
                assert not raised_exc

            case -1:
                assert mock_connect.call_count == settings.PUBLISH_MAX_RETRIES
                assert mock_close.call_count == settings.PUBLISH_MAX_RETRIES
                assert mock_logger.warning.call_count == settings.PUBLISH_MAX_RETRIES
                mock_logger.exception.assert_called_once_with(
                    "Failed to send message, max retries exceeded.", exc_info=pub_side_effect
                )
                assert {i * settings.PUBLISH_RETRY_BACKOFF_FACTOR for i in range(settings.PUBLISH_MAX_RETRIES)} == (
                    {call.args[0] for call in mock_sleep.call_args_list}
                )
                assert raised_exc == pub_side_effect

                # -------------------------------------- Warning --------------------------------------- #
                assert (
                    sum(i * settings.PUBLISH_RETRY_BACKOFF_FACTOR for i in range(settings.PUBLISH_MAX_RETRIES)) <= 1.5
                ), (
                    "Warning: this combination of PUBLISH_RETRY_BACKOFF_FACTOR and PUBLISH_MAX_RETRIES "
                    "can result in a wait time of over 1.5 seconds for a synchronous call. "
                    "If this is intentional, delete this assertion."
                )
                # -------------------------------------------------------------------------------------- #

            case _:
                assert mock_connect.call_count == expected_retry_n
                assert mock_close.call_count == expected_retry_n
                assert mock_logger.warning.call_count == expected_retry_n - 1
                mock_logger.exception.assert_not_called()
                assert {i * settings.PUBLISH_RETRY_BACKOFF_FACTOR for i in range(expected_retry_n)} == (
                    {call.args[0] for call in mock_sleep.call_args_list}
                )
                assert not raised_exc

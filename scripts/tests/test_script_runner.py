import re
from contextlib import contextmanager
from io import StringIO
from typing import TYPE_CHECKING, TypedDict
from unittest import mock

from django.test import TestCase

from scripts.management.commands.script_runner import Command
from user.tests.factories import ClientApplicationFactory, OrganisationFactory, UserFactory

if TYPE_CHECKING:

    class DefaultsType(TypedDict):
        script_name: str
        client_name: str
        exclude_test_users: bool
        batch_size: int
        log_path: str
        is_dry_run: bool


class TestClientDecommission(TestCase):
    loguru_set_file_sink_patcher = mock.patch("scripts.cli.client_decommission.loguru_set_file_sink")
    deleted_service_cleanup_patcher = mock.patch("scripts.cli.client_decommission.deleted_service_cleanup")
    defaults: "DefaultsType" = {
        "script_name": "client-decommission",
        "client_name": "Test",
        "exclude_test_users": False,
        "batch_size": 1000,
        "log_path": "decommission_logs.log",
        "is_dry_run": False,
    }

    @classmethod
    def setUpTestData(cls):
        org = OrganisationFactory(name="TestClientDecommission")
        cls.client_app = ClientApplicationFactory(name=cls.defaults["client_name"], organisation=org)
        cls.extra_client_app = ClientApplicationFactory(name="Other Client", organisation=org)

    def setUp(self) -> None:
        self.stdout = StringIO()
        self.script_runner = Command(stdout=self.stdout, stderr=StringIO())
        self.mock_set_sink = self.loguru_set_file_sink_patcher.start()
        self.mock_cleanup = self.deleted_service_cleanup_patcher.start()

    @contextmanager
    def handle_users_setup(self, selectable_users_n: int, extra_users_n: int = 0, test_users_n: int = 0):
        created_users = []
        for client_app, users_n, test_n in (
            (self.client_app, selectable_users_n, test_users_n),
            (self.extra_client_app, extra_users_n, 0),
        ):
            for _ in range(users_n):
                params = {}
                if test_n:
                    params = {
                        "is_tester": True,
                        "is_staff": True,
                    }
                    test_n -= 1

                user = UserFactory(client=client_app, **params)
                created_users.append(user)

        yield

        for user in created_users:
            user.delete()

    def test_dry_run(self):
        params = self.defaults | {"is_dry_run": True}

        for selectable_users_n, extra_users_n in (
            (0, 0),
            (2, 3),
            (0, 2),
            (3, 0),
        ):
            with self.handle_users_setup(selectable_users_n, extra_users_n):
                self.script_runner.handle(**params)

            output = self.stdout.getvalue()
            assert f"{selectable_users_n} users would be affected for client {self.client_app.name}" in output
            assert "Dry run completed no user was affected." in output
            self.mock_set_sink.assert_not_called()
            self.mock_cleanup.assert_not_called()
            self.stdout.truncate(0)

    def test_run_all_ok(self):
        params = self.defaults | {"is_dry_run": False}

        for selectable_users_n, extra_users_n in (
            (0, 0),
            (2, 3),
            (0, 2),
            (3, 0),
        ):
            with self.handle_users_setup(selectable_users_n, extra_users_n):
                self.script_runner.handle(**params)

            output = self.stdout.getvalue()
            assert "All users deleted successfully" in output
            self.mock_set_sink.assert_called_once()
            assert self.mock_cleanup.call_count == selectable_users_n
            self.mock_set_sink.reset_mock()
            self.mock_cleanup.reset_mock()
            self.stdout.truncate(0)

    def test_run_all_ok_exclude_test(self):
        params = self.defaults | {"is_dry_run": False, "exclude_test_users": True}

        for selectable_users_n, extra_users_n, test_users_n in (
            (0, 0, 0),
            (2, 3, 1),
            (0, 2, 0),
            (3, 0, 2),
        ):
            with self.handle_users_setup(selectable_users_n, extra_users_n, test_users_n):
                self.script_runner.handle(**params)

            output = self.stdout.getvalue()
            assert "All users deleted successfully" in output
            self.mock_set_sink.assert_called_once()
            assert self.mock_cleanup.call_count == selectable_users_n - test_users_n
            self.mock_set_sink.reset_mock()
            self.mock_cleanup.reset_mock()
            self.stdout.truncate(0)

    def test_run_some_failed(self):
        params = self.defaults | {"is_dry_run": False}
        output_lookup_re = re.compile(
            "Cleanup failed for users:\\n\[(.*)\]\\nlog details can be found in"  # noqa: W605
        )
        selectable_users_n = 3
        failed_n = 2
        for selectable_users_n, failed_n in (
            (0, 0),
            (3, 1),
            (2, 2),
        ):
            self.mock_cleanup.side_effect = [Exception("Test Error") for _ in range(failed_n)] + [
                None for _ in range(selectable_users_n - failed_n)
            ]

            with self.handle_users_setup(selectable_users_n):
                self.script_runner.handle(**params)

            output = self.stdout.getvalue()
            match failed_n:
                case 0:
                    assert "All users deleted successfully" in output
                case _:
                    failed_users = output_lookup_re.findall(output)[0]
                    assert len(failed_users.split(",")) == failed_n
                    assert f"log details can be found in {self.defaults['log_path']}" in output

            self.mock_set_sink.assert_called_once()
            assert self.mock_cleanup.call_count == selectable_users_n
            self.mock_set_sink.reset_mock()
            self.mock_cleanup.reset_mock()
            self.stdout.truncate(0)

    def tearDown(self) -> None:
        self.mock_set_sink.stop()
        self.mock_cleanup.stop()

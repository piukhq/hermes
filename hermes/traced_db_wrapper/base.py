import sentry_sdk
from django.db.backends.postgresql_psycopg2 import base

from django.conf import settings  # noqa


class DatabaseWrapper(base.DatabaseWrapper):

    def get_new_connection(self, conn_params):
        with sentry_sdk.start_span(op="get new db connection", description="get new db connection"):
            return super().get_new_connection(conn_params)

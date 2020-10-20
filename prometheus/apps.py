import logging
import os
import threading
import time
import urllib.error

from django.apps import AppConfig
from django.conf import settings
from prometheus_client import push_to_gateway
from prometheus_client.registry import REGISTRY

logger = logging.getLogger('ubiquity')


class PrometheusPushThread(threading.Thread):
    SLEEP_INTERVAL = 30
    PUSH_TIMEOUT = 3  # PushGateway should be running in the same pod

    def __init__(self, pid: str):
        # Grouping key should not need pod id as prometheus
        # should tag that itself
        self.grouping_key = {"pid": pid}
        super().__init__()

    def run(self):
        time.sleep(10)
        while True:
            now = time.time()
            try:
                push_to_gateway(
                    gateway=settings.PROMETHEUS_PUSH_GATEWAY,
                    job=settings.PROMETHEUS_JOB,
                    registry=REGISTRY,
                    grouping_key=self.grouping_key,
                    timeout=self.PUSH_TIMEOUT
                )
                logger.info("Pushed metrics to gateway")
            except (ConnectionRefusedError, urllib.error.URLError):
                logger.warning("Failed to push metrics, connection refused")
            except Exception as err:
                logger.exception("Caught exception whilst posting metrics", exc_info=err)

            remaining = self.SLEEP_INTERVAL - (time.time() - now)
            if remaining > 0:
                time.sleep(remaining)


class PrometheusPusherConfig(AppConfig):
    name = 'prometheus'

    def ready(self):
        logger.info("Configuring prometheus metric pusher")
        process_id = str(os.getpid())
        thread = PrometheusPushThread(process_id)
        thread.daemon = True
        thread.start()
        logger.info("Prometheus push thread started")

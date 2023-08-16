import logging

from celery import shared_task
from django.conf import settings

from hermes import redis

redis_client = redis.r_write

logger = logging.getLogger(__name__)

MPLANS_CACHE_DELETE_BATCH_SIZE = 20


@shared_task
def delete_membership_plans_cache() -> None:
    # Delete all caches for m_plan key slug including all by id ones
    try:
        pipe = redis_client.pipeline()
        for keys in redis_client.scan_iter(f"{settings.REDIS_MPLANS_CACHE_PREFIX}:*", MPLANS_CACHE_DELETE_BATCH_SIZE):
            pipe.delete(keys)
        pipe.execute()
    except Exception as ex:
        logger.exception("Failed to delete membership plans cache", exc_info=ex)
        raise ex

import logging

from aioredlock import Aioredlock

from pyartcd import redis

# This constant defines for each lock type:
# - how many times the lock manager should try to acquire the lock before giving up
# - the sleep interval between two consecutive retries, in seconds
# - a timeout, after which the lock will expire and clear itself
LOCK_POLICY = {
    # olm-bundle: give up after 1 hour
    'olm_bundle': {
        'retry_count': 36000,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 2,  # 2 hours
    },
    # mirror RPMs: give up after 1 hour
    'mirroring_rpms': {
        'retry_count': 36000,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 3,  # 3 hours
    },
    # compose: give up after 1 hour
    'compose': {
        'retry_count': 36000,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 6,  # 6 hours
    },
}


class LockManager(Aioredlock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('pyartcd')

    async def lock(self, resource, *args):
        self.logger.info('Trying to acquire lock %s', resource)
        lock = await super().lock(resource, *args)
        self.logger.info('Acquired resource %s', lock.resource)
        return lock

    async def unlock(self, lock):
        self.logger.info('Releasing lock "%s"', lock.resource)
        await super().unlock(lock)
        self.logger.info('Lock released')


def new_lock_manager(internal_lock_timeout=10.0, retry_count=3, retry_delay_min=0.1, use_ssl=True):
    """
    Builds and returns a new aioredlock.Aioredlock instance. Requires following env vars to be defined:
    - REDIS_SERVER_PASSWORD: authentication token to the Redis server
    - REDIS_HOST: hostname where Redis is deployed
    - REDIS_PORT: port where Redis is exposed

    If use_ssl is set, we assume Redis server is using a secure connection, and the protocol will be rediss://
    Otherwise, it will fall back to the unsecure redis://

    lock_timeout represents the "expiration date" of all the locks instantiated on this LockManager instance.
    If not set, it defaults to the library default

    retry_count is the number of attempts to acquire the lock. Once exceeded, the lock operation will throw an Exception
    retry_delay is the delay time in seconds between two consecutive attempts to acquire a resource

    Altogether, if the resource cannot be acquired in (retry_count * retry_delay), the lock operation will fail.
    """

    return LockManager(
        [redis.redis_url(use_ssl)],
        internal_lock_timeout=internal_lock_timeout,
        retry_count=retry_count,
        retry_delay_min=retry_delay_min
    )

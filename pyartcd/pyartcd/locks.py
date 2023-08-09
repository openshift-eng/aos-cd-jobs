import enum
import logging

from aioredlock import Aioredlock

from pyartcd import redis


# Defines the pipeline locks managed by Redis
class Lock(enum.Enum):
    def __str__(self):
        return f'{self.value}-lock'

    OLM_BUNDLE = 'olm-bundle'
    MIRRORING_RPMS = 'mirroring-rpms'
    COMPOSE = 'compose'
    GITHUB_ACTIVITY = 'github-activity'
    MASS_REBUILD = 'mass-rebuild-serializer'
    SIGNING = 'signing'


# This constant defines for each lock type:
# - how many times the lock manager should try to acquire the lock before giving up
# - the sleep interval between two consecutive retries, in seconds
# - a timeout, after which the lock will expire and clear itself
LOCK_POLICY = {
    # olm-bundle: give up after 1 hour
    Lock.OLM_BUNDLE: {
        'retry_count': 36000,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 2,  # 2 hours
    },
    # mirror RPMs: give up after 1 hour
    Lock.MIRRORING_RPMS: {
        'retry_count': 36000,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 3,  # 3 hours
    },
    # compose: give up after 1 hour
    Lock.COMPOSE: {
        'retry_count': 36000,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 6,  # 6 hours
    },
    # github-activity-lock: give up after 1 hour
    Lock.GITHUB_ACTIVITY: {
        'retry_count': 36000 * 1,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 6,  # 6 hours
    },
    # mass rebuild: give up after 8 hours
    Lock.MASS_REBUILD: {
        'retry_count': 36000 * 8,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 12,  # 12 hours
    },
    # signing: give up after 1 hour
    Lock.SIGNING: {
        'retry_count': 36000,
        'retry_delay_min': 0.1,
        'lock_timeout': 60 * 60 * 1,  # 1 hour
    }
}


class LockManager(Aioredlock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('pyartcd')

    @staticmethod
    def from_lock(lock: Lock, use_ssl=True):
        """
        Builds and returns a new aioredlock.Aioredlock instance. Requires following env vars to be defined:
        - REDIS_SERVER_PASSWORD: authentication token to the Redis server
        - REDIS_HOST: hostname where Redis is deployed
        - REDIS_PORT: port where Redis is exposed

        If use_ssl is set, we assume Redis server is using a secure connection, and the protocol will be rediss://
        Otherwise, it will fall back to the unsecure redis://

        'lock' identifies the desired lock from an Enum class. Each lock is associated with a 'lock_policy' object;
        'lock_policy' is a dictionary that maps the behavioral features of the lock manager.
         It needs to be structured as:

        lock_policy = {
            'retry_count': int,
            'retry_delay_min': float,
            'lock_timeout': float
        }

        where:
        - lock_timeout represents the expiration date in seconds
          of all the locks instantiated on this LockManager instance.
        - retry_count is the number of attempts to acquire the lock.
          If exceeded, the lock operation will throw an Exception
        - retry_delay is the delay time in seconds between two consecutive attempts to acquire a resource

        Altogether, if the resource cannot be acquired in (retry_count * retry_delay), the lock operation will fail.
        """

        lock_policy = LOCK_POLICY[lock]
        return LockManager(
            [redis.redis_url(use_ssl)],
            internal_lock_timeout=lock_policy['lock_timeout'],
            retry_count=lock_policy['retry_count'],
            retry_delay_min=lock_policy['retry_delay_min']
        )

    async def lock(self, resource, *args):
        self.logger.info('Trying to acquire lock %s', resource)
        lock = await super().lock(resource, *args)
        self.logger.info('Acquired resource %s', lock.resource)
        return lock

    async def unlock(self, lock):
        self.logger.info('Releasing lock "%s"', lock.resource)
        await super().unlock(lock)
        self.logger.info('Lock released')

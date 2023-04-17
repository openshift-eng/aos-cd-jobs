import os
from string import Template

from aioredlock import Aioredlock

# Redis instance where lock are stored
redis = Template('${protocol}://:${redis_password}@${redis_host}:${redis_port}')

# This constant defines a timeout for each kind of lock, after which the lock will expire and clear itself
LOCK_TIMEOUTS = {
    'olm-bundle': 60*60*2,  # 2 hours
}

# This constant defines how many times the lock manager should try to acquire the lock before giving up;
# it also defines the sleep interval between two consecutive retries, in seconds
RETRY_POLICY = {
    # olm-bundle: give up after 1 hour
    'olm_bundle': {
        'retry_count': 36000,
        'retry_delay_min': 0.1
    }
}


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

    redis_instance = redis.substitute(
        protocol='rediss' if use_ssl else 'redis',
        redis_password=os.environ['REDIS_SERVER_PASSWORD'],
        redis_host=os.environ['REDIS_HOST'],
        redis_port=os.environ['REDIS_PORT']
    )
    return Aioredlock(
        [redis_instance],
        internal_lock_timeout=internal_lock_timeout,
        retry_count=retry_count,
        retry_delay_min=retry_delay_min
    )

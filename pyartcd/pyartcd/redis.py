import logging
import os
from functools import wraps
from string import Template

import aioredis

logger = logging.getLogger(__name__)

# Redis instance template, to be renderes with env vars
redis = Template('${protocol}://:${redis_password}@${redis_host}:${redis_port}')


class RedisError(Exception):
    pass


def redis_url(use_ssl=True):
    if not os.environ.get('REDIS_SERVER_PASSWORD', None):
        raise RedisError('Please define REDIS_SERVER_PASSWORD env var')
    if not os.environ.get('REDIS_HOST', None):
        raise RedisError('Please define REDIS_HOST env var')
    if not os.environ.get('REDIS_PORT', None):
        raise RedisError('Please define REDIS_PORT env var')

    return redis.substitute(
        protocol='rediss' if use_ssl else 'redis',
        redis_password=os.environ['REDIS_SERVER_PASSWORD'],
        redis_host=os.environ['REDIS_HOST'],
        redis_port=os.environ['REDIS_PORT']
    )


def handle_connection(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        url = redis_url(use_ssl=True)
        conn = await aioredis.create_redis(url, encoding="utf-8")
        res = await func(conn, *args, **kwargs)
        conn.close()
        return res
    return wrapper


@handle_connection
async def get_value(conn: aioredis.commands.Redis, key: str):
    """
    Returns value for a given key
    """

    value = await conn.get(key)
    logger.debug('Key %s has value %s', key, value)
    return value


@handle_connection
async def set_value(conn: aioredis.commands.Redis, key: str, value):
    """
    Sets value for a key
    """

    logger.debug('Setting key %s to %s', key, value)
    await conn.set(key, value)


@handle_connection
async def get_keys(conn: aioredis.commands.Redis, pattern: str):
    """
    Returns a list of keys (string) matching pattern (e.g. "*.count")
    """

    keys = await conn.keys(pattern)
    logger.debug('Found keys matching pattern %s: %s', pattern, ', '.join(keys))
    return keys


@handle_connection
async def delete_key(conn: aioredis.commands.Redis, key: str):
    """
    Deletes given key from Redis DB
    """

    logger.debug('Deleting key %s', key)
    await conn.delete(key)

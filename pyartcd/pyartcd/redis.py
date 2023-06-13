import os
from string import Template

import aioredis

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


async def get_value(key: str, use_ssl: bool = True):
    url = redis_url(use_ssl)
    conn = await aioredis.create_redis(url, encoding="utf-8")
    value = await conn.get(key)
    conn.close()
    return value


async def set_value(key: str, value, use_ssl: bool = True):
    url = redis_url(use_ssl)
    conn = await aioredis.create_redis(url, encoding="utf-8")
    await conn.set(key, value)
    conn.close()

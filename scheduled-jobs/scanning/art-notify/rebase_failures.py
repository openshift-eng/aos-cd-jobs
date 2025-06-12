import asyncio

from artcommonlib import redis


async def get_rebase_failures():
    failures = {}

    async def _get_failures_for_engine(engine):
        redis_branch = f'count:rebase-failure:{engine}'
        print(f'Reading from {redis_branch}...')
        failed_images = await redis.get_keys(f'{redis_branch}:*')

        if failed_images:
            fail_counters = await redis.get_multiple_values(failed_images)
            for image, fail_counter in zip(failed_images, fail_counters):
                image_name = image.split(':')[-1]
                version = image.split(':')[-2]
                failures.setdefault(engine, {}).setdefault(version, {})[image_name] = fail_counter

    await asyncio.gather(*[_get_failures_for_engine(engine) for engine in ['brew', 'konflux']])
    return failures


if __name__ == '__main__':
    import asyncio

    async def main():
        print(await get_rebase_failures())
    asyncio.run(main())
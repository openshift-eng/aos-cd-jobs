import click

from pyartcd import redis
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime


@cli.command('cleanup-locks')
@click.option('--locks', required=True, help='Locks to be released on Redis')
@pass_runtime
@click_coroutine
async def cleanup_locks(runtime: Runtime, locks: str):
    locks_to_release = filter(lambda arg: arg, locks.split(','))

    for lock_name in locks_to_release:
        runtime.logger.warning('Deleting lock %s', lock_name)
        res = await redis.delete_key(lock_name)

        if res:
            runtime.logger.info('Lock %s deleted', lock_name)
        else:
            runtime.logger.warning('Lock %s could not be found', lock_name)

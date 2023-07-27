import click
import os
from pyartcd.runtime import Runtime
from pyartcd import exectools, cli


@cli.command('advisory-drop')
@click.option('--group', required=True, help='OCP group')
@click.option('--advisory', required=True, help='Advisory number')
@click.option('--comment', required=False, default="This bug will be dropped from current advisory because the advisory will also be dropped and not going to be shipped.",
              help='Comment will add to the bug attached on the advisory to explain the reason')
@pass_runtime
@click_coroutine
async def advisory_drop(runtime: Runtime, group: str, advisory: str, comment: str):
    # repair-bugs
    cmd = [
            'elliott',
            '--group', group,
            'repair-bugs',
            '--advisory', advisory,
            '--auto',
            '--comment', comment,
            '--close-placeholder',
            '--from', 'RELEASE_PENDING',
            '--to', 'VERIFIED',
        ]
    await exectools.cmd_assert_async(cmd, env=os.environ.copy())
    # drop advisory
    cmd = [
            'elliott',
            '--group', group,
            'advisory-drop', advisory,
        ]
    await exectools.cmd_assert_async(cmd, env=os.environ.copy())

import time
import click
import logging
from pyartcd import constants, exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime


_LOGGER = logging.getLogger(__name__)


@cli.group("imagestreams", short_help="Manage ART equivalent images in upstream CI.")
async def build_sync()
    pass


@build_sync.command('backup', short_help='Reads streams.yml and mirrors out ART equivalent images to api.ci.')
@pass_runtime
@click_coroutine
async def backup_imagestream():
    allNameSpaces = ["ocp", "ocp-priv", "ocp-s390x", "ocp-s390x-priv", "ocp-ppc64le", "ocp-ppc64le-priv", "ocp-arm64", "ocp-arm64-priv"]
    tar = tarfile.open("app.ci-backup.tgz","w:gz")
    for ns in allNameSpaces:
        cmd = f"oc --kubeconfig {constants.CIKUBECONFIG} get is -n {ns} -o yaml"
        _LOGGER.info("Running command: %s", cmd)
        _, stdout, _  = await exectools.cmd_gather_async(cmd)
        async with aiofiles.open(f"${ns}.backup.yaml", "w") as f:
            await f.write(stdout.read())
        tar.add(f"${ns}.backup.yaml")

        cmd = f"oc --kubeconfig {constants.CIKUBECONFIG} get secret/release-upgrade-graph -n ${ns} -o yaml"
        _LOGGER.info("Running command: %s", cmd)
        _, stdout, _  = await exectools.cmd_gather_async(cmd)
        async with aiofiles.open(f"${ns}.release-upgrade-graph.backup.yaml", "w") as f:
            await f.write(stdout.read())
        tar.add(f"${ns}.release-upgrade-graph.backup.yaml")
    tar.close()


@build_sync.command('trigger', short_help='Reads streams.yml and mirrors out ART equivalent images to api.ci.')
@click.option('--version', metavar='VERSION', required=True, help='OCP version')
@pass_runtime
@click_coroutine
async def trigger_release(version, dry_run):
    cmd = f"oc --kubeconfig {constants.CIKUBECONFIG} -n ocp tag registry.access.redhat.com/ubi8 {version}-art-latest:trigger-release-controller"
    _LOGGER.info("Running command: %s", cmd)
    await exectools.cmd_assert_async(cmd)
    time.sleep(10)
    cmd = f"oc --kubeconfig {constants.CIKUBECONFIG} -n ocp tag {version}-art-latest:trigger-release-controller -d"
    _LOGGER.info("Running command: %s", cmd)
    await exectools.cmd_assert_async(cmd)


@build_sync.command('update', short_help='Reads streams.yml and mirrors out ART equivalent images to api.ci.')
@click.option('--doozer_data_path', metavar='Doozer_data_path', required=True, help='doozer_data_path dir')
@click.option('--doozer_working_dir', metavar='Doozer_working_dir', required=True, help='doozer_working dir')
@click.option('--build_version', metavar='BUILD_VERSION', required=True, help='OCP version')
@click.option('--assembly', metavar='Assembly', required=True, help='assembly args can be version or stream')
@click.option('--imagelist', metavar='Imagelist', required=False, default=None, help='(Optional) Limited list of images to sync, for testing purposes')
@click.option('--excludeArches', metavar='excludeArches', required=False, help='(Optional) List of problem arch(es) NOT to sync (aarch64, ppc64le, s390x, x86_64)')
@click.option('--dry_run', required=False, is_flag=True, help='mock running oc command')
@click.option('--emergency_ignore_issues', required=False, is_flag=True, help='Ignore all issues with constructing payload. Do not use without approval.')
@click.option('--publish', required=False, is_flag=True, help='Publish release image(s) directly to registry.ci for testing')
@click.option('--debug', required=False, is_flag=True, help='Run "oc" commands with greater logging')
@pass_runtime
@click_coroutine
def update_imagestream(runtime, imagelist, doozer_data_path, doozer_working_dir, build_version,assembly, excludeArches, dry_run, emergency_ignore_issues, publish, debug):
    output_dir = f"{runtime.working_dir}/gen-payload-artifacts"
    excludeArchesParam = excludeArches or ""
    assembly_type = assembly or "stream"
    images = f"--images {imagelist}" if imagelist else ""
    dryRunParams = "--skip-gc-tagging --moist-run" if dry_run else ""
    emegency_ignore = "--emergency-ignore-issues" if emergency_ignore_issues else ""
    publish = "--publish" if publish else ""
    debug = "--loglevel=5" if debug else ""
    cmd = [
        "doozer",
        debug,
        "--assembly", assembly_type,
        images,
        "--working-dir", doozer_working_dir,
        "--data-path", doozer_data_path,
        "--group", f"openshift-{build_version}",
        "--output-dir", output_dir,
        "release:gen-payload",
        "--apply",
        publish,
        excludeArchesParam,
        dryRunParams,
        EMERGENCY_IGNORE_ISSUES
    ]
    _LOGGER.info("Running command: %s", cmd)
    await exectools.cmd_assert_async(cmd)

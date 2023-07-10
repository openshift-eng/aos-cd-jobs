import asyncio
import glob
import json
import os

import click
import yaml

from pyartcd.cli import cli, pass_runtime, click_coroutine
from pyartcd.oc import registry_login
from pyartcd.redis import RedisError
from pyartcd.runtime import Runtime
from pyartcd import exectools, constants, redis, util
from pyartcd.util import branch_arches
from doozerlib.util import go_suffix_for_arch

GEN_PAYLOAD_ARTIFACTS_OUT_DIR = 'gen-payload-artifacts'


class BuildSyncPipeline:
    def __init__(self, runtime: Runtime, version: str, assembly: str, publish: bool, data_path: str,
                 emergency_ignore_issues: bool, retrigger_current_nightly: bool, doozer_data_gitref: str,
                 debug: bool, images: str, exclude_arches: str, skip_multiarch_payload: bool):
        self.runtime = runtime
        self.version = version
        self.assembly = assembly
        self.publish = publish
        self.data_path = data_path
        self.emergency_ignore_issues = emergency_ignore_issues
        self.retrigger_current_nightly = retrigger_current_nightly
        self.doozer_data_gitref = doozer_data_gitref
        self.debug = debug
        self.images = images
        self.exclude_arches = [] if not exclude_arches else exclude_arches.replace(',', ' ').split()
        self.skip_multiarch_payload = skip_multiarch_payload
        self.logger = runtime.logger
        self.working_dir = self.runtime.working_dir

    async def run(self):
        # Make sure we're logged into the OC registry
        await registry_login(self.runtime)

        # Should we retrigger current nightly?
        if self.retrigger_current_nightly:
            await self._retrigger_current_nightly()
            return

        # Backup imagestreams
        self.logger.info('Backup all imagestreams...')
        await self._backup_all_imagestreams()

        # Update nightly imagestreams
        self.logger.info('Update nightly imagestreams...')
        await self._update_nightly_imagestreams()

    async def _retrigger_current_nightly(self):
        """
        Forces the release controller to re-run with existing images, by marking the current ImageStream as new
        again for Release Controller. No change will be made to payload images in the release.
        The purpose of triggering current nightly again is to run tests again on an already existing nightly.
        """

        if self.assembly != 'stream':
            raise RuntimeError('Cannot use with assembly other than stream. Exiting.')

        if self.runtime.dry_run:
            self.logger.info('Would have triggered new release cut in release controller.')
            return

        self.logger.info('Triggering release controller to cut new release using previously synced builds...')
        cmd = f'oc --kubeconfig {os.environ["KUBECONFIG"]} -n ocp tag registry.access.redhat.com/ubi8 ' \
              f'{self.version}-art-latest:trigger-release-controller'
        _, out, _, = await exectools.cmd_gather_async(cmd)
        self.logger.info('oc output: %s', out)

        self.logger.info('Sleeping so that release controller has time to react...')
        await asyncio.sleep(60)

        cmd = f'oc --kubeconfig {os.environ["KUBECONFIG"]} -n ocp tag ' \
              f'{self.version}-art-latest:trigger-release-controller -d'
        _, out, _, = await exectools.cmd_gather_async(cmd)
        self.logger.info('oc output: %s', out)

    async def _backup_all_imagestreams(self):
        """
        An incident where a bug in oc destroyed the content of a critical imagestream ocp:is/release uncovered the fact
        that this vital data was not being backed up by any process. DPTP will be asked to backup etcd on this cluster,
        but ART should also begin backing up these imagestreams during normal operations as a first line of defense.
        In the build-sync job, prior to updating the 4.x-art-latest imagestreams, a copy of all imagestreams in the
        various release controller namespaces should be performed.
        """

        @exectools.limit_concurrency(500)
        async def backup_namespace(ns):
            self.logger.info('Running backup for namespace %s', ns)

            # Backup the imagestream
            _, stdout, _ = await exectools.cmd_gather_async(
                f'oc --kubeconfig {os.environ["KUBECONFIG"]} get is -n {ns} -o yaml')
            with open(f'{ns}.backup.yaml', 'w') as f:
                f.write(stdout)

            # Backup the upgrade graph for the releases
            _, stdout, _ = await exectools.cmd_gather_async(
                f'oc --kubeconfig {os.environ["KUBECONFIG"]} get secret/release-upgrade-graph -n {ns} -o yaml')
            with open(f'{ns}.release-upgrade-graph.backup.yaml', 'w') as f:
                f.write(stdout)

            self.logger.info('Backup completed for namespace %s', ns)

        namespaces = ['ocp', 'ocp-priv', 'ocp-s390x', 'ocp-s390x-priv', 'ocp-ppc64le',
                      'ocp-ppc64le-priv', 'ocp-arm64', 'ocp-arm64-priv']

        tasks = []
        for namespace in namespaces:
            tasks.append(backup_namespace(namespace))
        await asyncio.gather(*tasks)

        # Create tar archive
        self.logger.info('Creating backup archives')
        cmd = ['tar', 'zcvf', 'app.ci-backup.tgz']
        cmd.extend(glob.glob('*.backup.yaml'))
        await exectools.cmd_assert_async(cmd)

        # Remove *.yaml
        self.logger.debug('Removing yaml files')
        cmd = ['rm']
        cmd.extend(glob.glob('*.backup.yaml'))
        await exectools.cmd_assert_async(cmd)

    async def _tags_to_transfer(self) -> list:
        """
        Gather a list of tags to mirror to the CI imagestream. This will include rhel-coreos*
        to pick up any future RHCOS RHEL versions (e.g. rhel-coreos-8 and rhel-coreos[-extensions] starting with RHEL9).
        """

        cmd = f'oc --kubeconfig {os.environ["KUBECONFIG"]} get -n ocp is/{self.version}-art-latest -o=json'
        _, out, _ = await exectools.cmd_gather_async(cmd)
        tags = json.loads(out)['spec']['tags']
        tags_to_transfer = [tag['name'] for tag in tags if 'machine-os-content' in tag['name'] or 'rhel-coreos' in tag['name']]
        return tags_to_transfer

    @exectools.limit_concurrency(500)
    async def _tag_into_ci_imagestream(self, arch_suffix, tag):
        # isolate the pullspec trom the ART imagestream tag
        # (e.g. quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:<sha>)
        cmd = f'oc --kubeconfig {os.environ["KUBECONFIG"]} -n ocp{arch_suffix} ' \
              f'get istag/{self.version}-art-latest{arch_suffix}:{tag} -o=json'
        _, out, _ = await exectools.cmd_gather_async(cmd)
        tag_pullspec = json.loads(out)['tag']['from']['name']

        # tag the pull spec into the CI imagestream (is/4.x) with the same tag name.
        self.logger.info('Tagging ocp%s/%s:%s with %s',
                         arch_suffix, self.version, tag, tag_pullspec)
        cmd = f'oc --kubeconfig {os.environ["KUBECONFIG"]} -n ocp{arch_suffix} ' \
              f'tag {tag_pullspec} {self.version}:{tag}'
        await exectools.cmd_gather_async(cmd)

        if not arch_suffix:
            # Tag the image into the imagestream for private CI from openshift-priv.
            self.logger.info('Tagging ocp-private/%s-priv:%s with %s',
                             self.version, tag, tag_pullspec)
            cmd = f'oc --kubeconfig {os.environ["KUBECONFIG"]} -n ocp-private ' \
                  f'tag {tag_pullspec} {self.version}-priv:{tag}'
            await exectools.cmd_gather_async(cmd)

    async def _populate_ci_imagestreams(self):
        """"
        Starting with 4.12, ART is responsible for populating the CI imagestream (-n ocp is/4.12) with
        references to the latest machine-os-content, rhel-coreos-8, rhel-coreos-8-extensions (and
        potentially more with rhel9). If this is failing, it must be treated as a priority since
        CI will begin falling being nightly CoreOS content.
        """

        # Only for applicable versions
        major, minor = [int(n) for n in self.version.split('.')]
        if major <= 4 and minor < 12:
            return

        # Only for stream assembly and openshift-{MAJOR}.{MINOR} branches
        if not self.assembly == 'stream' or self.doozer_data_gitref:
            return

        try:
            supported_arches = await branch_arches(
                group=f'openshift-{self.version}',
                assembly=self.assembly
            )
            tags_to_transfer: list = await self._tags_to_transfer()

            tasks = []
            for arch in supported_arches:
                arch_suffix = go_suffix_for_arch(arch)
                for tag in tags_to_transfer:
                    tasks.append(self._tag_into_ci_imagestream(arch_suffix, tag))
            await asyncio.gather(*tasks)

        except (ChildProcessError, KeyError) as e:
            slack_client = self.runtime.new_slack_client()
            slack_client.bind_channel(f'openshift-{self.version}')
            await slack_client.say(
                f'Unable to mirror CoreOS images to CI for {self.version}: {e}')

    async def _update_nightly_imagestreams(self):
        """
        Determine the content to update in the ART latest imagestreams and apply those changes on the CI cluster.
        The verb will also mirror out images to the quay monorepo.
        """

        self.logger.info('Generating and applying imagestream updates')
        mirror_working = 'MIRROR_working'

        # Run release:gen-payload
        cmd = [
            'doozer',
            f'--assembly={self.assembly}']
        if self.images:
            cmd.append(f'--images={self.images}')
        cmd.extend([
            f'--working-dir={mirror_working}',
            f'--data-path={self.data_path}'
        ])
        group_param = f'--group=openshift-{self.version}'
        if self.doozer_data_gitref:
            group_param += f'@{self.doozer_data_gitref}'
        cmd.append(group_param)
        cmd.extend([
            'release:gen-payload',
            f'--output-dir={GEN_PAYLOAD_ARTIFACTS_OUT_DIR}',
            '--apply'
        ])
        if self.emergency_ignore_issues:
            cmd.append('--emergency-ignore-issues')
        if not self.skip_multiarch_payload:
            cmd.append('--apply-multi-arch')
        if self.exclude_arches:
            cmd.extend([f'--exclude-arch {arch}' for arch in self.exclude_arches])
        if self.runtime.dry_run:
            cmd.extend(['--skip-gc-tagging', '--moist-run'])
        await exectools.cmd_assert_async(cmd)

        # Populate CI imagestreams
        await self._populate_ci_imagestreams()

        if self.publish:
            # Run 'oc adm release new' in parallel
            tasks = []
            for filename in glob.glob(f'{GEN_PAYLOAD_ARTIFACTS_OUT_DIR}/updated-tags-for.*.yaml'):
                tasks.append(self._publish(filename))
            await asyncio.gather(*tasks)

    @exectools.limit_concurrency(500)
    async def _publish(self, filename):
        with open(filename) as f:
            meta = yaml.safe_load(f.read())['metadata']
            namespace = meta['namespace']
            reponame = namespace.replace('ocp', 'release')
            name = f'{self.version}.0-{self.assembly}'  # must be semver
            image = f'registry.ci.openshift.org/{namespace}/{reponame}:{name}'

            # Build new Openshift release image
            cmd = f'oc adm release new --to-image={image} --name {name} ' \
                  f'--reference-mode=source -n {namespace} --from-image-stream {meta["name"]}'

            if self.runtime.dry_run:
                self.logger.info('Would have created the release image as follows: %s', cmd)
                return

            # Retry up to 3 times, to get past flakes
            for attempt in range(3):
                try:
                    await exectools.cmd_assert_async(cmd)
                    self.logger.info('Published image %s', image)
                    break  # command succeeded
                except ChildProcessError as e:
                    if attempt == 2:
                        raise
                    self.logger.info('Command failed: retrying, %s', e)
                    await asyncio.sleep(5)


@cli.command('build-sync')
@click.option("--version", required=True,
              help="The OCP version to sync")
@click.option("--assembly", required=True, default="stream",
              help="The name of an assembly to sync")
@click.option("--publish", is_flag=True,
              help="Publish release image(s) directly to registry.ci for testing")
@click.option("--data-path", required=True, default=constants.OCP_BUILD_DATA_URL,
              help="ocp-build-data fork to use (e.g. assembly definition in your own fork)")
@click.option("--emergency-ignore-issues", is_flag=True,
              help="Ignore all issues with constructing payload. Do not use without approval.")
@click.option("--retrigger-current-nightly", is_flag=True,
              help="Forces the release controller to re-run with existing images. No change will be made to payload"
                   "images in the release")
@click.option("--data-gitref", required=False,
              help="(Optional) Doozer data path git [branch / tag / sha] to use")
@click.option("--debug", is_flag=True,
              help="Run \"oc\" commands with greater logging")
@click.option("--images", required=False,
              help="(Optional) Comma-separated list of images to sync, for testing purposes")
@click.option("--exclude-arches", required=False,
              help="(Optional) Comma-separated list of arches NOT to sync (aarch64, ppc64le, s390x, x86_64)")
@click.option("--skip-multiarch-payload", is_flag=True,
              help="If group/assembly has multi_arch.enabled, you can bypass --apply-multi-arch and the generation of a"
                   "heterogeneous release payload by setting this to true")
@pass_runtime
@click_coroutine
async def build_sync(runtime: Runtime, version: str, assembly: str, publish: bool, data_path: str,
                     emergency_ignore_issues: bool, retrigger_current_nightly: bool, data_gitref: str,
                     debug: bool, images: str, exclude_arches: str, skip_multiarch_payload: bool):
    pipeline = BuildSyncPipeline(
        runtime=runtime,
        version=version,
        assembly=assembly,
        publish=publish,
        data_path=data_path,
        emergency_ignore_issues=emergency_ignore_issues,
        retrigger_current_nightly=retrigger_current_nightly,
        doozer_data_gitref=data_gitref,
        debug=debug,
        images=images,
        exclude_arches=exclude_arches,
        skip_multiarch_payload=skip_multiarch_payload
    )
    fail_count_name = f'{version}-assembly.{assembly}.count'

    try:
        await pipeline.run()

        #  All good: reset fail count to 0
        await redis.set_value(fail_count_name, 0)
        runtime.logger.info('Fail count "%s" set to 0', fail_count_name)

    except (RuntimeError, ChildProcessError):
        # Increment failure count
        current_count = await redis.get_value(fail_count_name)
        if current_count is None:
            current_count = 0
        fail_count = int(current_count) + 1
        runtime.logger.info('Failure count for %s: %s', version, fail_count)

        # Update fail counter on Redis
        await redis.set_value(fail_count_name, fail_count)

        # Less than 2 failures, assembly != stream: just break the build
        if fail_count < 2 or assembly != 'stream':
            raise

        # More than 2 failures: we need to notify ART and #forum-relase before breaking the build
        slack_client = runtime.new_slack_client()
        msg = f'Pipeline has failed to assemble release payload for {version} (assembly {assembly}) {fail_count} times.'

        # TODO https://issues.redhat.com/browse/ART-5657
        if 10 <= fail_count <= 50:
            art_notify_frequency = 5
            forum_release_notify_frequency = 10

        elif 50 <= fail_count <= 200:
            art_notify_frequency = 10
            forum_release_notify_frequency = 50

        elif fail_count > 200:
            art_notify_frequency = 100
            forum_release_notify_frequency = 100

        else:
            # Default notify frequency
            art_notify_frequency = 2
            forum_release_notify_frequency = 5

        # Spam ourselves a little more often than forum-release
        if fail_count % art_notify_frequency == 0:
            slack_client.bind_channel(f'openshift-{version}')
            await slack_client.say(msg)

        if fail_count % forum_release_notify_frequency == 0:
            group_config = await util.load_group_config(group=f'openshift-{version}', assembly=assembly)

            # For GA releases, let forum-release know why no new builds
            if group_config['release_state']['release']:
                slack_client.bind('#forum-release').say(msg)

        raise

    except RedisError as e:
        runtime.logger.error('Encountered error when updating the fail counter: %s', e)
        raise

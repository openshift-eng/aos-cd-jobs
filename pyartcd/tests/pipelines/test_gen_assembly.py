import asyncio
from collections import OrderedDict
import os
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from pyartcd.pipelines.gen_assembly import GenAssemblyPipeline


class TestGenAssemblyPipeline(IsolatedAsyncioTestCase):
    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "a b c", ""))
    def test_get_nightlies(self, cmd_gather_async: AsyncMock):
        runtime = MagicMock()
        pipeline = GenAssemblyPipeline(runtime, "openshift-4.12", "4.12.99", "https://example.com/ocp-build-data.git",
                                       nightlies=(), allow_pending=False, allow_rejected=False,
                                       allow_inconsistency=False, custom=False, arches=(), in_flight=None,
                                       previous_list=(), auto_previous=True)
        actual = asyncio.run(pipeline._get_nightlies())
        self.assertEqual(actual, ["a", "b", "c"])
        cmd_gather_async.assert_awaited_once_with(
            ['doozer', '--group', 'openshift-4.12', '--assembly', 'stream', 'get-nightlies'], stderr=None, env=ANY)

        cmd_gather_async.reset_mock()
        pipeline.allow_pending = True
        pipeline.allow_inconsistency = True
        pipeline.allow_rejected = True
        actual = asyncio.run(pipeline._get_nightlies())
        self.assertEqual(actual, ["a", "b", "c"])
        cmd_gather_async.assert_awaited_once_with(
            ['doozer', '--group', 'openshift-4.12', '--assembly', 'stream', 'get-nightlies', '--allow-pending',
             '--allow-rejected', '--allow-inconsistency'], stderr=None, env=ANY)

        cmd_gather_async.reset_mock()
        pipeline.arches = ("x86_64", "aarch64")
        pipeline.custom = True
        pipeline.nightlies = ("n1", "n2")
        actual = asyncio.run(pipeline._get_nightlies())
        self.assertEqual(actual, ["a", "b", "c"])
        cmd_gather_async.assert_awaited_once_with(
            ['doozer', '--group', 'openshift-4.12', '--assembly', 'stream', '--arches', 'x86_64,aarch64',
             'get-nightlies', '--allow-pending', '--allow-rejected', '--allow-inconsistency', '--matching=n1',
             '--matching=n2'], stderr=None, env=ANY)

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True)
    def test_gen_assembly_from_releases(self, cmd_gather_async: AsyncMock):
        runtime = MagicMock()
        pipeline = GenAssemblyPipeline(runtime, "openshift-4.12", "4.12.99", "https://example.com/ocp-build-data.git",
                                       nightlies=(), allow_pending=False, allow_rejected=False,
                                       allow_inconsistency=False, custom=False, arches=(), in_flight="4.11.88",
                                       previous_list=(), auto_previous=True)
        out = """
releases:
  4.12.99:
    assembly:
      basis:
        brew_event: 123456
        reference_releases:
          aarch64: nightly1
          ppc64le: nightly2
          s390x: nightly3
          x86_64: nightly4
      group:
        advisories:
          extras: -1
          image: -1
          metadata: -1
          rpm: -1
        release_jira: ART-0
        upgrades: 4.11.1,4.11.2,4.11.3,4.11.88
      members:
        images: []
        rpms: []
      rhcos:
        machine-os-content:
          images:
            aarch64: registry.example.com/rhcos@sha256:606487eb3c86e011412820dd52db558e68ac09106e209953d596619c6f6b0287
            ppc64le: registry.example.com/rhcos@sha256:e8a5656fbedd12c1a9e2c8c182c87e0f35546ef6828204f5b00dd7d3859c6c88
            s390x: registry.example.com/rhcos@sha256:16b6c9da7d8b23b57d6378a9de36fd21455147f3e27d5fe5ee8864852b31065a
            x86_64: registry.example.com/rhcos@sha256:b2e3b0ef40b7ad82b7e4107c1283baca71397b757d3e429ceefc6b1514e19848
      type: standard
        """.strip()
        cmd_gather_async.return_value = (0, out, "")
        candidate_nightlies = ["nightly1", "nightly2", "nightly3", "nightly4"]
        actual = asyncio.run(pipeline._gen_assembly_from_releases(candidate_nightlies))
        self.assertIn("4.12.99", actual["releases"])

    @patch("os.environ", return_value={"GITHUB_TOKEN": "deadbeef"})
    @patch("pathlib.Path.exists", autospec=True, return_value=True)
    @patch("pyartcd.pipelines.gen_assembly.GhApi")
    @patch("pyartcd.pipelines.gen_assembly.yaml")
    @patch("pyartcd.pipelines.gen_assembly.GitRepository", autospec=True)
    def test_create_or_update_pull_request(self, git_repo: MagicMock, yaml: MagicMock, gh_api: MagicMock, *_):
        runtime = MagicMock(dry_run=False, config={"build_config": {
            "ocp_build_data_repo_push_url": "git@github.com:someone/ocp-build-data.git",
        }})
        pipeline = GenAssemblyPipeline(runtime, "openshift-4.12", "4.12.99", "https://example.com/ocp-build-data.git",
                                       nightlies=(), allow_pending=False, allow_rejected=False,
                                       allow_inconsistency=False, custom=False, arches=(), in_flight=None,
                                       previous_list=(), auto_previous=True)
        pipeline._working_dir = Path("/path/to/working")
        yaml.load.return_value = OrderedDict([
            ("releases", OrderedDict([
                ("4.12.98", OrderedDict()),
                ("4.12.97", OrderedDict()),
            ]))
        ])
        fn = MagicMock(return_value=OrderedDict([
            ("releases", OrderedDict([
                ("4.12.99", OrderedDict()),
                ("4.12.98", OrderedDict()),
                ("4.12.97", OrderedDict()),
            ]))
        ]))
        git_repo.return_value.commit_push.return_value = True
        api = gh_api.return_value
        api.pulls.list.return_value = MagicMock(items=[])
        api.pulls.create.return_value = MagicMock(html_url="https://github.example.com/foo/bar/pull/1234", number=1234)
        actual = asyncio.run(pipeline._create_or_update_pull_request(fn))
        self.assertEqual(actual.number, 1234)
        git_repo.return_value.setup.assert_awaited_once_with("git@github.com:someone/ocp-build-data.git")
        git_repo.return_value.fetch_switch_branch.assert_awaited_once_with(
            'auto-gen-assembly-openshift-4.12-4.12.99', 'openshift-4.12')
        yaml.load.assert_called_once_with(pipeline._working_dir / 'ocp-build-data-push/releases.yml')
        git_repo.return_value.commit_push.assert_awaited_once_with(ANY)
        api.pulls.create.assert_called_once_with(head='someone:auto-gen-assembly-openshift-4.12-4.12.99',
                                                 base='openshift-4.12', title='Add assembly 4.12.99', body=ANY,
                                                 maintainer_can_modify=True)

    @patch("pyartcd.pipelines.gen_assembly.GenAssemblyPipeline._create_or_update_pull_request", autospec=True,
           return_value=MagicMock(html_url="https://github.example.com/foo/bar/pull/1234", number=1234))
    @patch("pyartcd.pipelines.gen_assembly.GenAssemblyPipeline._gen_assembly_from_releases", autospec=True)
    @patch("pyartcd.pipelines.gen_assembly.GenAssemblyPipeline._get_nightlies", autospec=True)
    async def test_run(self, get_nightlies: AsyncMock, _gen_assembly_from_releases: AsyncMock,
                       _create_or_update_pull_request: AsyncMock):

        os.environ["GITHUB_TOKEN"] = "irrelevant"

        runtime = MagicMock(dry_run=False, config={"build_config": {
            "ocp_build_data_repo_push_url": "git@github.com:someone/ocp-build-data.git",
        }})
        runtime.new_slack_client.return_value = AsyncMock()
        runtime.new_slack_client.return_value.say.return_value = {'message': {'ts': ''}}
        runtime.new_slack_client.return_value.bind_channel = MagicMock()

        pipeline = GenAssemblyPipeline(runtime, "openshift-4.12", "4.12.99", "https://example.com/ocp-build-data.git",
                                       nightlies=(), allow_pending=False, allow_rejected=False,
                                       allow_inconsistency=False, custom=False, arches=(), in_flight=None,
                                       previous_list=(), auto_previous=True)
        pipeline._working_dir = Path("/path/to/working")
        get_nightlies.return_value = ["nightly1", "nightly2", "nightly3", "nightly4"]
        _gen_assembly_from_releases.return_value = OrderedDict([
            ("releases", OrderedDict([("4.12.99", OrderedDict())])),
        ])
        await pipeline.run()
        get_nightlies.assert_awaited_once_with(pipeline)
        _gen_assembly_from_releases.assert_awaited_once_with(pipeline, ['nightly1', 'nightly2', 'nightly3', 'nightly4'])
        _create_or_update_pull_request.assert_awaited_once_with(pipeline, ANY)
        del os.environ["GITHUB_TOKEN"]

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch
from pyartcd import constants
from pyartcd.pipelines.rebuild import (PlashetBuildResult, RebuildPipeline, RebuildType)


class TestRebuildPipeline(IsolatedAsyncioTestCase):
    @patch("pyartcd.exectools.cmd_gather_async")
    def test_ocp_build_data_url(self, cmd_gather_async: Mock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, dry_run=False)
        fork_url = 'https://fork.com/ocp-build-data-fork.git'
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None, ocp_build_data_url=fork_url)
        actual = pipeline._doozer_env_vars["DOOZER_DATA_PATH"]
        expected = fork_url
        self.assertEqual(actual, expected)

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.rmtree")
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_build_plashet_from_tags(self, cmd_assert_async: AsyncMock, rmtree: Mock, path_exists: Mock, path_mkdir: Mock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None, ocp_build_data_url='')
        tag_pvs = [("fake-tag-candidate", "FAKE-PRODUCT-VERSION")]
        embargoed_tags = ["fake-tag-embargoed"]
        actual = await pipeline._build_plashet_from_tags("plashet1234", "plashet1234", 8, ["x86_64", "s390x"], tag_pvs, embargoed_tags, 12345)
        expected_local_dir = runtime.working_dir / "plashets/el8/art0001/plashet1234"
        expected_remote_url = constants.PLASHET_REMOTE_URL + "/4.9-el8/art0001/plashet1234"
        self.assertEqual(actual, ("plashet1234", expected_local_dir, expected_remote_url))
        path_exists.assert_called_once_with()
        rmtree.assert_called_once_with(expected_local_dir)
        path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "config:plashet", "--base-dir", "/path/to/working/plashets/el8/art0001", "--name", "plashet1234", "--repo-subdir", "os", "--arch", "x86_64", "signed", "--arch", "s390x", "signed", "from-tags", "--signing-advisory-id", "12345", "--signing-advisory-mode", "clean", "--include-embargoed", "--inherit", "--embargoed-brew-tag", "fake-tag-embargoed", "--brew-tag", 'fake-tag-candidate', 'FAKE-PRODUCT-VERSION']
        cmd_assert_async.assert_awaited_once_with(excepted_doozer_cmd, env=ANY)

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.rmtree")
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_build_plashet_for_assembly_rhcos(self, cmd_assert_async: AsyncMock, rmtree: Mock, path_exists: Mock, path_mkdir: Mock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None, ocp_build_data_url='')
        actual = await pipeline._build_plashet_for_assembly("plashet1234", "plashet1234", 8, ["x86_64", "s390x"], 12345)
        expected_local_dir = runtime.working_dir / "plashets/el8/art0001/plashet1234"
        expected_remote_url = constants.PLASHET_REMOTE_URL + "/4.9-el8/art0001/plashet1234"
        self.assertEqual(actual, ("plashet1234", expected_local_dir, expected_remote_url))
        path_exists.assert_called_once_with()
        rmtree.assert_called_once_with(expected_local_dir)
        path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        excepted_doozer_cmd = ['doozer', '--group', 'openshift-4.9', '--assembly', 'art0001', 'config:plashet', '--base-dir', '/path/to/working/plashets/el8/art0001', '--name', 'plashet1234', '--repo-subdir', 'os', '--arch', 'x86_64', 'signed', '--arch', 's390x', 'signed', 'for-assembly', '--signing-advisory-id', '12345', '--signing-advisory-mode', 'clean', '--el-version', '8', '--rhcos']
        cmd_assert_async.assert_awaited_once_with(excepted_doozer_cmd, env=ANY)

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.rmtree")
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_build_plashet_for_assembly_image(self, cmd_assert_async: AsyncMock, rmtree: Mock, path_exists: Mock, path_mkdir: Mock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        actual = await pipeline._build_plashet_for_assembly("plashet1234", "plashet1234", 8, ["x86_64", "s390x"], 12345)
        expected_local_dir = runtime.working_dir / "plashets/el8/art0001/plashet1234"
        expected_remote_url = constants.PLASHET_REMOTE_URL + "/4.9-el8/art0001/plashet1234"
        self.assertEqual(actual, ("plashet1234", expected_local_dir, expected_remote_url))
        path_exists.assert_called_once_with()
        rmtree.assert_called_once_with(expected_local_dir)
        path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        excepted_doozer_cmd = ['doozer', '--group', 'openshift-4.9', '--assembly', 'art0001', 'config:plashet', '--base-dir', '/path/to/working/plashets/el8/art0001', '--name', 'plashet1234', '--repo-subdir', 'os', '--arch', 'x86_64', 'signed', '--arch', 's390x', 'signed', 'for-assembly', '--signing-advisory-id', '12345', '--signing-advisory-mode', 'clean', '--el-version', '8', '--image', 'foo']
        cmd_assert_async.assert_awaited_once_with(excepted_doozer_cmd, env=ANY)

    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_copy_plashet_out_to_remote(self, cmd_assert_async: AsyncMock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None, ocp_build_data_url='')
        local_plashet_dir = "/path/to/local/plashets/el8/plashet1234"
        await pipeline._copy_plashet_out_to_remote(8, local_plashet_dir, "building")
        cmd_assert_async.assert_any_await(
            ['ssh', 'ocp-artifacts', '--', 'ln', '-sfn', '--', 'plashet1234',
             '/mnt/data/pub/RHOCP/plashets/4.9-el8/art0001/building'])
        cmd_assert_async.assert_any_await(
            ["rsync", "-av", "--links", "--progress", "-h", "--no-g", "--omit-dir-times", "--chmod=Dug=rwX,ugo+r",
             "--perms", "--", "/path/to/local/plashets/el8/plashet1234",
             f"{constants.PLASHET_REMOTE_HOST}:{constants.PLASHET_REMOTE_BASE_DIR}/4.9-el8/art0001"])
        cmd_assert_async.assert_any_await(
            ["ssh", constants.PLASHET_REMOTE_HOST, "--", "ln", "-sfn", "--",
             "plashet1234", f"{constants.PLASHET_REMOTE_BASE_DIR}/4.9-el8/art0001/building"])

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_for_assembly")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_from_tags")
    async def test_build_plashets_rhcos(self, _build_plashet_from_tags: AsyncMock, _build_plashet_for_assembly: AsyncMock):
        runtime = MagicMock(dry_run=False)
        group_config = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
        }
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None, ocp_build_data_url='')
        _build_plashet_from_tags.return_value = PlashetBuildResult("plashet1", Path("/path/to/local/dir1"), "https://example.com/dir1")
        _build_plashet_for_assembly.return_value = PlashetBuildResult("plashet2", Path("/path/to/local/dir2"), "https://example.com/dir2")
        actual = await pipeline._build_plashets("202107160000", 8, group_config, None)
        _build_plashet_from_tags.assert_awaited_once_with('plashet-rebuild-basis', 'art0001-202107160000-rhcos-basis', 8, group_config["arches"], (('rhaos-4.9-rhel-8-candidate', 'OSE-4.9-RHEL-8'),), ['rhaos-4.9-rhel-8-embargoed'], group_config["signing_advisory"])
        _build_plashet_for_assembly.assert_awaited_once_with('plashet-rebuild-overrides', 'art0001-202107160000-rhcos-overrides', 8, group_config["arches"], group_config["signing_advisory"])
        self.assertEqual(actual, [("plashet1", Path("/path/to/local/dir1"), "https://example.com/dir1"), ("plashet2", Path("/path/to/local/dir2"), "https://example.com/dir2")])

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_for_assembly")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_from_tags")
    async def test_build_plashets_image(self, _build_plashet_from_tags: AsyncMock, _build_plashet_for_assembly: AsyncMock):
        runtime = MagicMock(dry_run=False)
        group_config = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
        }
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        _build_plashet_from_tags.return_value = PlashetBuildResult("plashet1", Path("/path/to/local/dir1"), "https://example.com/dir1")
        _build_plashet_for_assembly.return_value = PlashetBuildResult("plashet2", Path("/path/to/local/dir2"), "https://example.com/dir2")
        image_config = {"enabled_repos": ["rhel-8-server-ose-rpms-embargoed", "rhel-8-server-ironic-rpms"]}
        actual = await pipeline._build_plashets("202107160000", 8, group_config, image_config)
        _build_plashet_from_tags.assert_any_await('rhel-8-server-ose-rpms-embargoed', 'art0001-202107160000-image-foo-basis', 8, group_config["arches"], (('rhaos-4.9-rhel-8-candidate', 'OSE-4.9-RHEL-8'),), ['rhaos-4.9-rhel-8-embargoed'], group_config["signing_advisory"])
        _build_plashet_from_tags.assert_any_await('rhel-8-server-ironic-rpms', 'art0001-202107160000-image-foo-ironic', 8, group_config["arches"], (('rhaos-4.9-ironic-rhel-8-candidate', 'OSE-IRONIC-4.9-RHEL-8'),), ['rhaos-4.9-rhel-8-embargoed'], group_config["signing_advisory"])
        _build_plashet_for_assembly.assert_awaited_once_with('plashet-rebuild-overrides', 'art0001-202107160000-image-foo-overrides', 8, group_config["arches"], group_config["signing_advisory"])
        self.assertEqual(actual, [("plashet1", Path("/path/to/local/dir1"), "https://example.com/dir1"), ("plashet1", Path("/path/to/local/dir1"), "https://example.com/dir1"), ("plashet2", Path("/path/to/local/dir2"), "https://example.com/dir2")])

    @patch("pathlib.Path.read_text")
    def test_generate_repo_file_for_image(self, read_text: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        plashets = [
            PlashetBuildResult("rhel-8-server-ose", "fake-basis", "https://example.com/plashets/4.9-el8/art0001/fake-basis"),
            PlashetBuildResult("plashet-rebuild-basis2", "fake-basis2", "https://example.com/plashets/4.9-el8/art0001/fake-basis2"),
            PlashetBuildResult("plashet-rebuild-overrides", "fake-overrides", "https://example.com/plashets/4.9-el8/art0001/fake-overrides"),
        ]
        read_text.return_value = """
[rhel-8-server-ose]
enabled=1
gpgcheck=0
baseurl=https://example.com/plashets/4.9-el8/art0001/building-embargoed/$basearch/os

[rhel-8-server-ose-x86_64]
enabled=1
gpgcheck=0
baseurl=https://example.com/plashets/4.9-el8/art0001/building-embargoed/x86_64/os

[rhel-8-server-ose-s390x]
enabled=1
gpgcheck=0
baseurl=https://example.com/plashets/4.9-el8/art0001/building-embargoed/s390x/os

[fake-external-repo]
enabled=1
gpgcheck=0
baseurl=https://example.com/fake-external-repo/$basearch/os
        """.strip()
        out_file = StringIO()
        pipeline._generate_repo_file_for_image(out_file, plashets, ["x86_64", "s390x"])
        expected = """
# These repositories are generated by the OpenShift Automated Release Team
# https://issues.redhat.com/browse/ART-3154

[fake-external-repo]
enabled = 1
gpgcheck = 0
baseurl = https://example.com/fake-external-repo/$basearch/os

[rhel-8-server-ose]
name = rhel-8-server-ose
baseurl = https://example.com/plashets/4.9-el8/art0001/fake-basis/$basearch/os
enabled = 1
gpgcheck = 1
gpgkey = file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release

[plashet-rebuild-basis2]
name = plashet-rebuild-basis2
baseurl = https://example.com/plashets/4.9-el8/art0001/fake-basis2/$basearch/os
enabled = 1
gpgcheck = 1
gpgkey = file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release

[plashet-rebuild-overrides]
name = plashet-rebuild-overrides
baseurl = https://example.com/plashets/4.9-el8/art0001/fake-overrides/$basearch/os
enabled = 1
gpgcheck = 0
priority = 1
        """.strip()
        self.assertEqual(out_file.getvalue().strip(), expected)
        read_text.assert_called_once()

    def test_generate_repo_file_for_rhcos(self):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None, ocp_build_data_url='')
        out_file = StringIO()
        plashets = [
            PlashetBuildResult("plashet-rebuild-basis", "fake-basis", "https://example.com/plashets/4.9-el8/art0001/fake-basis"),
            PlashetBuildResult("plashet-rebuild-overrides", "fake-overrides", "https://example.com/plashets/4.9-el8/art0001/fake-overrides"),
        ]
        pipeline._generate_repo_file_for_rhcos(out_file, plashets)
        expected = """
# These repositories are generated by the OpenShift Automated Release Team
# https://issues.redhat.com/browse/ART-3154

[plashet-rebuild-basis]
name = plashet-rebuild-basis
baseurl = https://example.com/plashets/4.9-el8/art0001/fake-basis/$basearch/os
enabled = 1
gpgcheck = 0

[plashet-rebuild-overrides]
name = plashet-rebuild-overrides
baseurl = https://example.com/plashets/4.9-el8/art0001/fake-overrides/$basearch/os
enabled = 1
gpgcheck = 0
priority = 1
        """.strip()
        self.assertEqual(out_file.getvalue().strip(), expected)

    @patch("pyartcd.exectools.cmd_gather_async")
    async def test_get_meta_config(self, cmd_gather_async: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        cmd_gather_async.return_value = (0, """
images:
  foo:
    some_key: some_value
        """.strip(), "")
        actual = await pipeline._get_meta_config()
        cmd_gather_async.assert_called_once_with(["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "-i", "foo", "config:print", "--yaml"], env=ANY)
        self.assertEqual(actual, {"some_key": "some_value"})

    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_rebase_image(self, cmd_assert_async: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        await pipeline._rebase_image("202107160000.p?")
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:rebase", "--version", "v4.9", "--release", "202107160000.p?", "--force-yum-updates", "--message", "Updating Dockerfile version and release v4.9-202107160000.p?", "--push"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

        runtime.dry_run = True
        cmd_assert_async.reset_mock()
        await pipeline._rebase_image("202107160000.p?")
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:rebase", "--version", "v4.9", "--release", "202107160000.p?", "--force-yum-updates", "--message", "Updating Dockerfile version and release v4.9-202107160000.p?"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    @patch("builtins.open")
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_build_image(self, cmd_assert_async: Mock, open: Mock):
        runtime = MagicMock(dry_run=False, working_dir=Path("/path/to/working"))
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        repo_url = "http://example.com/plashets/4.9-el8/art0001/art0001-image-foo-overrides/rebuild.repo"
        open.return_value.__enter__.return_value = StringIO("build|nvrs=foo-container-v1.2.3-1.p0.assembly.art0001|")
        nvrs = await pipeline._build_image(repo_url)
        self.assertEqual(nvrs, ["foo-container-v1.2.3-1.p0.assembly.art0001"])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:build", "--repo", "http://example.com/plashets/4.9-el8/art0001/art0001-image-foo-overrides/rebuild.repo"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)
        open.assert_called_once_with(runtime.working_dir / "doozer-working/record.log", "r")

        runtime.dry_run = True
        cmd_assert_async.reset_mock()
        nvrs = await pipeline._build_image(repo_url)
        self.assertEqual(nvrs, [])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:build", "--repo", "http://example.com/plashets/4.9-el8/art0001/art0001-image-foo-overrides/rebuild.repo", "--dry-run"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    @patch("builtins.open")
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_rebase_and_build_rpm(self, cmd_assert_async: Mock, open: Mock):
        runtime = MagicMock(dry_run=False, working_dir=Path("/path/to/working"))
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RPM, dg_key="foo", ocp_build_data_url='')
        release = "202107160000.p?"
        open.return_value.__enter__.return_value = StringIO("build_rpm|nvrs=foo-v1.2.3-202107160000.p0.assembly.art0001.el8,foo-v1.2.3-202107160000.p0.assembly.art0001.el7|")
        nvrs = await pipeline._rebase_and_build_rpm(release)
        self.assertEqual(nvrs, ["foo-v1.2.3-202107160000.p0.assembly.art0001.el8", "foo-v1.2.3-202107160000.p0.assembly.art0001.el7"])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "-r", "foo", "rpms:rebase-and-build", "--version", "4.9", "--release", release]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)
        open.assert_called_once_with(runtime.working_dir / "doozer-working/record.log", "r")

        runtime.dry_run = True
        cmd_assert_async.reset_mock()
        nvrs = await pipeline._rebase_and_build_rpm(release)
        self.assertEqual(nvrs, [])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "-r", "foo", "rpms:rebase-and-build", "--version", "4.9", "--release", release, "--dry-run"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    def test_generate_example_schema_rpm(self):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RPM, dg_key="foo", ocp_build_data_url='')
        actual = pipeline._generate_example_schema(["foo-v1.2.3-1.el8", "foo-v1.2.3-1.el7"])
        expected = {
            "releases": {
                "art0001": {
                    "assembly": {
                        "members": {
                            "rpms": [{
                                "distgit_key": "foo",
                                "metadata": {
                                    "is": {
                                        "el8": "foo-v1.2.3-1.el8",
                                        "el7": "foo-v1.2.3-1.el7",
                                    }
                                }
                            }]
                        }
                    }
                }
            }
        }
        self.assertEqual(actual, expected)

    def test_generate_example_schema_image(self):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        actual = pipeline._generate_example_schema(["foo-container-v1.2.3-1"])
        expected = {
            "releases": {
                "art0001": {
                    "assembly": {
                        "members": {
                            "images": [{
                                "distgit_key": "foo",
                                "metadata": {
                                    "is": {
                                        "nvr": "foo-container-v1.2.3-1",
                                    }
                                }
                            }]
                        }
                    }
                }
            }
        }
        self.assertEqual(actual, expected)

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._generate_example_schema")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._rebase_and_build_rpm")
    @patch("pyartcd.pipelines.rebuild.datetime")
    @patch("pyartcd.pipelines.rebuild.load_releases_config")
    @patch("pyartcd.pipelines.rebuild.load_group_config")
    async def test_run_rpm(self, load_group_config: AsyncMock, load_releases_config: AsyncMock, mock_datetime: Mock, _rebase_and_build_rpm: Mock, _generate_example_schema: Mock):
        mock_datetime.utcnow.return_value = datetime(2021, 7, 16, 0, 0, 0, 0, tzinfo=timezone.utc)
        runtime = MagicMock(dry_run=False)
        load_group_config.return_value = {}
        load_releases_config.return_value = {
            "releases": {
                "art0001": {
                    "assembly": {
                        "type": "custom"
                    }
                }
            }
        }
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RPM, dg_key="foo", ocp_build_data_url='')
        _rebase_and_build_rpm.return_value = ["foo-v1.2.3-1.el8", "foo-v1.2.3-1.el7"]
        _generate_example_schema.return_value = {"some_key": "some_value"}
        await pipeline.run()
        load_group_config.assert_awaited_once_with("openshift-4.9", "art0001", env=ANY)
        load_releases_config.assert_awaited_once()
        _rebase_and_build_rpm.assert_called_once_with("202107160000.p?")
        _generate_example_schema.assert_called_once_with(_rebase_and_build_rpm.return_value)

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._generate_example_schema")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_image")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._copy_plashet_out_to_remote")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._generate_repo_file_for_image")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._rebase_image")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashets")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._get_meta_config")
    @patch("pyartcd.pipelines.rebuild.load_releases_config")
    @patch("pyartcd.pipelines.rebuild.load_group_config")
    @patch("builtins.open")
    @patch("pyartcd.pipelines.rebuild.datetime")
    async def test_run_image(self, mock_datetime: Mock, open: Mock, load_group_config: AsyncMock, load_releases_config: AsyncMock,
                       _get_meta_config: AsyncMock, _build_plashets: AsyncMock, _rebase_image: AsyncMock,
                       _generate_repo_file_for_image: Mock, _copy_plashet_out_to_remote: AsyncMock, _build_image: AsyncMock, _generate_example_schema: Mock):
        mock_datetime.utcnow.return_value = datetime(2021, 7, 16, 0, 0, 0, 0, tzinfo=timezone.utc)
        timestamp = mock_datetime.utcnow.return_value.strftime("%Y%m%d%H%M")
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo", ocp_build_data_url='')
        group_config = load_group_config.return_value = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
            "branch": "rhaos-4.9-rhel-8"
        }
        load_releases_config.return_value = {
            "releases": {
                "art0001": {
                    "assembly": {
                        "type": "custom"
                    }
                }
            }
        }
        image_meta = _get_meta_config.return_value = {
            "enabled_repos": ["fake-basis"]
        }
        plashets = _build_plashets.return_value = [
            PlashetBuildResult("fake-basis", Path("/path/to/local/dir1"), "https://example.com/dir1"),
            PlashetBuildResult("plashet-rebuild-overrides", Path("/path/to/local/dir2"), "https://example.com/dir2"),
        ]
        _build_image.return_value = ["foo-container-v1.2.3-1"]
        _generate_example_schema.return_value = {"some_key": "some_value"}
        await pipeline.run()
        load_group_config.assert_awaited_once_with("openshift-4.9", "art0001", env=ANY)
        load_releases_config.assert_awaited_once()
        _build_plashets.assert_awaited_once_with(timestamp, 8, group_config, image_meta)
        _rebase_image.assert_awaited_once_with(f"{timestamp}.p?")
        open.assert_called_once_with(Path("/path/to/local/dir2/rebuild.repo"), "w")
        _generate_repo_file_for_image.assert_called_once_with(open.return_value.__enter__.return_value, plashets, group_config["arches"])
        _copy_plashet_out_to_remote.assert_any_await(8, Path("/path/to/local/dir1"))
        _copy_plashet_out_to_remote.assert_any_await(8, Path("/path/to/local/dir2"))
        _build_image.assert_awaited_once_with("https://example.com/dir2/rebuild.repo")
        _generate_example_schema.assert_called_once_with(_build_image.return_value)

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._copy_plashet_out_to_remote")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._generate_repo_file_for_rhcos")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashets")
    @patch("pyartcd.pipelines.rebuild.load_releases_config")
    @patch("pyartcd.pipelines.rebuild.load_group_config")
    @patch("builtins.open")
    @patch("pyartcd.pipelines.rebuild.datetime")
    async def test_run_rhcos(self, mock_datetime: Mock, open: Mock, load_group_config: AsyncMock, load_releases_config: AsyncMock, _build_plashets: AsyncMock,
                       _generate_repo_file_for_rhcos: Mock, _copy_plashet_out_to_remote: AsyncMock):
        mock_datetime.utcnow.return_value = datetime(2021, 7, 16, 0, 0, 0, 0, tzinfo=timezone.utc)
        timestamp = mock_datetime.utcnow.return_value.strftime("%Y%m%d%H%M")
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None, ocp_build_data_url='')
        group_config = load_group_config.return_value = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
            "branch": "rhaos-4.9-rhel-8"
        }
        load_releases_config.return_value = {
            "releases": {
                "art0001": {
                    "assembly": {
                        "type": "custom"
                    }
                }
            }
        }
        plashets = _build_plashets.return_value = [
            PlashetBuildResult("fake-basis", Path("/path/to/local/dir1"), "https://example.com/dir1"),
            PlashetBuildResult("plashet-rebuild-overrides", Path("/path/to/local/dir2"), "https://example.com/dir2"),
        ]
        await pipeline.run()
        load_group_config.assert_awaited_once_with("openshift-4.9", "art0001", env=ANY)
        load_releases_config.assert_awaited_once()
        _build_plashets.assert_awaited_once_with(timestamp, 8, group_config, None)
        open.assert_called_once_with(Path("/path/to/local/dir2/rebuild.repo"), "w")
        _generate_repo_file_for_rhcos.assert_called_once_with(open.return_value.__enter__.return_value, plashets)
        _copy_plashet_out_to_remote.assert_any_await(8, Path("/path/to/local/dir1"))
        _copy_plashet_out_to_remote.assert_any_await(8, Path("/path/to/local/dir2"))

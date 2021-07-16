from asyncio import get_event_loop
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest import TestCase

from mock import ANY, AsyncMock, MagicMock, Mock
from mock.mock import patch
from pyartcd import constants
from pyartcd.pipelines.rebuild import RebuildPipeline, RebuildType
from pyartcd.runtime import Runtime


class TestRebuildPipeline(TestCase):
    @patch("pyartcd.exectools.cmd_gather_async")
    def test_load_group_config(self, cmd_gather_async: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None)
        group_config_content = """
        key: "value"
        """
        cmd_gather_async.return_value = (0, group_config_content, "")
        actual = get_event_loop().run_until_complete(pipeline._load_group_config())
        cmd_gather_async.assert_called_once_with(["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "config:read-group", "--yaml"], env=ANY)
        self.assertEqual(actual["key"], "value")

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.rmtree")
    @patch("pyartcd.exectools.cmd_assert_async")
    def test_build_plashet_from_tags(self, cmd_assert_async: Mock, rmtree: Mock, path_exists: Mock, path_mkdir: Mock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None)
        actual = get_event_loop().run_until_complete(pipeline._build_plashet_from_tags("plashet1234", 8, ["x86_64", "s390x"], 12345))
        expected_local_dir = runtime.working_dir / "plashets/el8/art0001/plashet1234"
        expected_remote_url = constants.PLASHET_REMOTE_URL + "/4.9-el8/art0001/plashet1234"
        self.assertEqual(actual, (expected_local_dir, expected_remote_url))
        path_exists.assert_called_once_with()
        rmtree.assert_called_once_with(expected_local_dir)
        path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "config:plashet", "--base-dir", "/path/to/working/plashets/el8/art0001", "--name", "plashet1234", "--repo-subdir", "os", "--arch", "x86_64", "signed", "--arch", "s390x", "signed", "from-tags", "--signing-advisory-id", "12345", "--signing-advisory-mode", "clean", "--include-embargoed", "--inherit", "--embargoed-brew-tag", "rhaos-4.9-rhel-8-embargoed", "--brew-tag", "rhaos-4.9-rhel-8-candidate", "OSE-4.9-RHEL-8"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.rmtree")
    @patch("pyartcd.exectools.cmd_assert_async")
    def test_build_plashet_for_assembly_rhcos(self, cmd_assert_async: Mock, rmtree: Mock, path_exists: Mock, path_mkdir: Mock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None)
        actual = get_event_loop().run_until_complete(pipeline._build_plashet_for_assembly("plashet1234", 8, ["x86_64", "s390x"], 12345))
        expected_local_dir = runtime.working_dir / "plashets/el8/art0001/plashet1234"
        expected_remote_url = constants.PLASHET_REMOTE_URL + "/4.9-el8/art0001/plashet1234"
        self.assertEqual(actual, (expected_local_dir, expected_remote_url))
        path_exists.assert_called_once_with()
        rmtree.assert_called_once_with(expected_local_dir)
        path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        excepted_doozer_cmd = ['doozer', '--group', 'openshift-4.9', '--assembly', 'art0001', 'config:plashet', '--base-dir', '/path/to/working/plashets/el8/art0001', '--name', 'plashet1234', '--repo-subdir', 'os', '--arch', 'x86_64', 'signed', '--arch', 's390x', 'signed', 'for-assembly', '--signing-advisory-id', '12345', '--signing-advisory-mode', 'clean', '--el-version', '8', '--rhcos']
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("shutil.rmtree")
    @patch("pyartcd.exectools.cmd_assert_async")
    def test_build_plashet_for_assembly_image(self, cmd_assert_async: Mock, rmtree: Mock, path_exists: Mock, path_mkdir: Mock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
        actual = get_event_loop().run_until_complete(pipeline._build_plashet_for_assembly("plashet1234", 8, ["x86_64", "s390x"], 12345))
        expected_local_dir = runtime.working_dir / "plashets/el8/art0001/plashet1234"
        expected_remote_url = constants.PLASHET_REMOTE_URL + "/4.9-el8/art0001/plashet1234"
        self.assertEqual(actual, (expected_local_dir, expected_remote_url))
        path_exists.assert_called_once_with()
        rmtree.assert_called_once_with(expected_local_dir)
        path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        excepted_doozer_cmd = ['doozer', '--group', 'openshift-4.9', '--assembly', 'art0001', 'config:plashet', '--base-dir', '/path/to/working/plashets/el8/art0001', '--name', 'plashet1234', '--repo-subdir', 'os', '--arch', 'x86_64', 'signed', '--arch', 's390x', 'signed', 'for-assembly', '--signing-advisory-id', '12345', '--signing-advisory-mode', 'clean', '--el-version', '8', '--image', 'foo']
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    @patch("pyartcd.exectools.cmd_assert_async")
    def test_copy_plashet_out_to_remote(self, cmd_assert_async: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None)
        local_plashet_dir = "/path/to/local/plashets/el8/plashet1234"
        get_event_loop().run_until_complete(pipeline._copy_plashet_out_to_remote(8, local_plashet_dir, "building"))
        cmd_assert_async.assert_any_call(["ssh", constants.PLASHET_REMOTE_HOST, "--", "mkdir", "-p", "--", "/mnt/rcm-guest/puddles/RHAOS/plashets/4.9-el8/art0001"])
        cmd_assert_async.assert_any_call(["rsync", "-av", "--links", "--progress", "-h", "--no-g", "--omit-dir-times", "--chmod=Dug=rwX,ugo+r", "--perms", "--", "/path/to/local/plashets/el8/plashet1234", f"{constants.PLASHET_REMOTE_HOST}:{constants.PLASHET_REMOTE_BASE_DIR}/4.9-el8/art0001"])
        cmd_assert_async.assert_any_call(["ssh", constants.PLASHET_REMOTE_HOST, "--", "ln", "-sfn", "--", "plashet1234", f"{constants.PLASHET_REMOTE_BASE_DIR}/4.9-el8/art0001/building"])

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_for_assembly")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_from_tags")
    def test_build_plashets_rhcos(self, _build_plashet_from_tags: AsyncMock, _build_plashet_for_assembly: AsyncMock):
        runtime = MagicMock(dry_run=False)
        group_config = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
        }
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None)
        _build_plashet_from_tags.return_value = (Path("/path/to/local/dir1"), "https://example.com/dir1")
        _build_plashet_for_assembly.return_value = (Path("/path/to/local/dir2"), "https://example.com/dir2")
        actual = get_event_loop().run_until_complete(pipeline._build_plashets("202107160000", 8, group_config))
        _build_plashet_from_tags.assert_called_once_with('art0001-202107160000-rhcos-basis', 8, group_config["arches"], group_config["signing_advisory"])
        _build_plashet_for_assembly.assert_called_once_with('art0001-202107160000-rhcos-overrides', 8, group_config["arches"], group_config["signing_advisory"])
        self.assertEqual(actual, (Path("/path/to/local/dir1"), "https://example.com/dir1", Path("/path/to/local/dir2"), "https://example.com/dir2"))

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_for_assembly")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashet_from_tags")
    def test_build_plashets_image(self, _build_plashet_from_tags: AsyncMock, _build_plashet_for_assembly: AsyncMock):
        runtime = MagicMock(dry_run=False)
        group_config = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
        }
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
        _build_plashet_from_tags.return_value = (Path("/path/to/local/dir1"), "https://example.com/dir1")
        _build_plashet_for_assembly.return_value = (Path("/path/to/local/dir2"), "https://example.com/dir2")
        actual = get_event_loop().run_until_complete(pipeline._build_plashets("202107160000", 8, group_config))
        _build_plashet_from_tags.assert_called_once_with('art0001-202107160000-image-foo-basis', 8, group_config["arches"], group_config["signing_advisory"])
        _build_plashet_for_assembly.assert_called_once_with('art0001-202107160000-image-foo-overrides', 8, group_config["arches"], group_config["signing_advisory"])
        self.assertEqual(actual, (Path("/path/to/local/dir1"), "https://example.com/dir1", Path("/path/to/local/dir2"), "https://example.com/dir2"))

    @patch("pathlib.Path.read_text")
    def test_generate_repo_file_for_image(self, read_text: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
        read_text.return_value = """
[rhel-8-server-ose]
enabled=1
gpgcheck=0
baseurl=http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/plashets/4.9-el8/art0001/building-embargoed/$basearch/os
        """.strip()
        out_file = StringIO()
        pipeline._generate_repo_file_for_image(out_file, "fake-basis", "https://example.com/plashets/4.9-el8/art0001/fake-overrides")
        expected = """
[rhel-8-server-ose]
enabled=1
gpgcheck=0
baseurl=http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/plashets/4.9-el8/art0001/fake-basis/$basearch/os
[plashet-rebuild-overrides]
name = plashet-rebuild-overrides
baseurl = https://example.com/plashets/4.9-el8/art0001/fake-overrides/$basearch/os
enabled = 1
priority = 1
gpgcheck = 1
gpgkey = file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release
        """.strip()
        self.assertEqual(out_file.getvalue().strip(), expected)

    def test_generate_repo_file_for_rhcos(self):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None)
        out_file = StringIO()
        pipeline._generate_repo_file_for_rhcos(out_file, "fake-basis", "https://example.com/plashets/4.9-el8/art0001/fake-overrides")
        expected = """
# These repositories are generated by the OpenShift Automated Release Team
# https://issues.redhat.com/browse/ART-3154

[plashet-rebuild-basis]
name = plashet-rebuild-basis
baseurl = fake-basis/$basearch/os
enabled = 1
gpgcheck = 0
exclude=nss-altfiles kernel protobuf
[plashet-rebuild-overrides]
name = plashet-rebuild-overrides
baseurl = https://example.com/plashets/4.9-el8/art0001/fake-overrides/$basearch/os
enabled = 1
priority = 1
gpgcheck = 0
exclude=nss-altfiles kernel protobuf
        """.strip()
        self.assertEqual(out_file.getvalue().strip(), expected)

    @patch("pyartcd.exectools.cmd_gather_async")
    def test_get_image_distgit_branch(self, cmd_gather_async: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
        group_config = {
            "branch": "rhaos-4.9-rhel-8",
        }
        cmd_gather_async.return_value = (0, """
images:
  foo: rhaos-4.9-rhel-7
        """.strip(), "")
        actual = get_event_loop().run_until_complete(pipeline._get_image_distgit_branch(group_config))
        cmd_gather_async.assert_called_once_with(["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "-i", "foo", "config:print", "--yaml", "--key", "distgit.branch"], env=ANY)
        self.assertEqual(actual, "rhaos-4.9-rhel-7")

        cmd_gather_async.reset_mock()
        cmd_gather_async.return_value = (0, """
images:
  foo: null
        """.strip(), "")
        actual = get_event_loop().run_until_complete(pipeline._get_image_distgit_branch(group_config))
        cmd_gather_async.assert_called_once_with(["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "-i", "foo", "config:print", "--yaml", "--key", "distgit.branch"], env=ANY)
        self.assertEqual(actual, "rhaos-4.9-rhel-8")

    @patch("pyartcd.exectools.cmd_assert_async")
    def test_rebase_image(self, cmd_assert_async: Mock):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
        get_event_loop().run_until_complete(pipeline._rebase_image("202107160000.p?"))
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:rebase", "--version", "v4.9", "--release", "202107160000.p?", "--force-yum-updates", "--message", "Updating Dockerfile version and release v4.9-202107160000.p?", "--push"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

        runtime.dry_run = True
        cmd_assert_async.reset_mock()
        get_event_loop().run_until_complete(pipeline._rebase_image("202107160000.p?"))
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:rebase", "--version", "v4.9", "--release", "202107160000.p?", "--force-yum-updates", "--message", "Updating Dockerfile version and release v4.9-202107160000.p?"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    @patch("builtins.open")
    @patch("pyartcd.exectools.cmd_assert_async")
    def test_build_image(self, cmd_assert_async: Mock, open: Mock):
        runtime = MagicMock(dry_run=False, working_dir=Path("/path/to/working"))
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
        repo_url = "http://example.com/plashets/4.9-el8/art0001/art0001-image-foo-overrides/rebuild.repo"
        open.return_value.__enter__.return_value = StringIO("build|nvrs=foo-container-v1.2.3-1.p0.assembly.art0001|")
        nvrs = get_event_loop().run_until_complete(pipeline._build_image(repo_url))
        self.assertEqual(nvrs, ["foo-container-v1.2.3-1.p0.assembly.art0001"])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:build", "--repo", "http://example.com/plashets/4.9-el8/art0001/art0001-image-foo-overrides/rebuild.repo"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)
        open.assert_called_once_with(runtime.working_dir / "doozer-working/record.log", "r")

        runtime.dry_run = True
        cmd_assert_async.reset_mock()
        nvrs = get_event_loop().run_until_complete(pipeline._build_image(repo_url))
        self.assertEqual(nvrs, [])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "--latest-parent-version", "-i", "foo", "images:build", "--repo", "http://example.com/plashets/4.9-el8/art0001/art0001-image-foo-overrides/rebuild.repo", "--dry-run"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    @patch("builtins.open")
    @patch("pyartcd.exectools.cmd_assert_async")
    def test_rebase_and_build_rpm(self, cmd_assert_async: Mock, open: Mock):
        runtime = MagicMock(dry_run=False, working_dir=Path("/path/to/working"))
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RPM, dg_key="foo")
        release = "202107160000.p?"
        open.return_value.__enter__.return_value = StringIO("build_rpm|nvrs=foo-v1.2.3-202107160000.p0.assembly.art0001.el8,foo-v1.2.3-202107160000.p0.assembly.art0001.el7|")
        nvrs = get_event_loop().run_until_complete(pipeline._rebase_and_build_rpm(release))
        self.assertEqual(nvrs, ["foo-v1.2.3-202107160000.p0.assembly.art0001.el8", "foo-v1.2.3-202107160000.p0.assembly.art0001.el7"])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "-r", "foo", "rpms:rebase-and-build", "--version", "4.9", "--release", release]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)
        open.assert_called_once_with(runtime.working_dir / "doozer-working/record.log", "r")

        runtime.dry_run = True
        cmd_assert_async.reset_mock()
        nvrs = get_event_loop().run_until_complete(pipeline._rebase_and_build_rpm(release))
        self.assertEqual(nvrs, [])
        excepted_doozer_cmd = ["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "-r", "foo", "rpms:rebase-and-build", "--version", "4.9", "--release", release, "--dry-run"]
        cmd_assert_async.assert_called_once_with(excepted_doozer_cmd, env=ANY)

    def test_generate_example_schema_rpm(self):
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RPM, dg_key="foo")
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
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
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
    def test_run_rpm(self, mock_datetime: Mock, _rebase_and_build_rpm: Mock, _generate_example_schema: Mock):
        mock_datetime.utcnow.return_value = datetime(2021, 7, 16, 0, 0, 0, 0, tzinfo=timezone.utc)
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RPM, dg_key="foo")
        _rebase_and_build_rpm.return_value = ["foo-v1.2.3-1.el8", "foo-v1.2.3-1.el7"]
        _generate_example_schema.return_value = {"some_key": "some_value"}
        get_event_loop().run_until_complete(pipeline.run())
        _rebase_and_build_rpm.assert_called_once_with("202107160000.p?")
        _generate_example_schema.assert_called_once_with(_rebase_and_build_rpm.return_value)

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._generate_example_schema")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_image")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._copy_plashet_out_to_remote")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._generate_repo_file_for_image")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._rebase_image")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashets")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._get_image_distgit_branch")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._load_group_config")
    @patch("builtins.open")
    @patch("pyartcd.pipelines.rebuild.datetime")
    def test_run_image(self, mock_datetime: Mock, open: Mock, _load_group_config: Mock, _get_image_distgit_branch: Mock, _build_plashets: Mock, _rebase_image: Mock,
                       _generate_repo_file_for_image: Mock, _copy_plashet_out_to_remote: Mock, _build_image: Mock, _generate_example_schema: Mock):
        mock_datetime.utcnow.return_value = datetime(2021, 7, 16, 0, 0, 0, 0, tzinfo=timezone.utc)
        timestamp = mock_datetime.utcnow.return_value.strftime("%Y%m%d%H%M")
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.IMAGE, dg_key="foo")
        group_config = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
        }
        _load_group_config.return_value = group_config
        _get_image_distgit_branch.return_value = "rhaos-4.9-rhel-8"
        _build_plashets.return_value = (Path("/path/to/plashet-a"), "http://example.com/plashet-a", Path("/path/to/plashet-b"), "http://example.com/plashet-b")
        _build_image.return_value = ["foo-container-v1.2.3-1"]
        _generate_example_schema.return_value = {"some_key": "some_value"}
        get_event_loop().run_until_complete(pipeline.run())
        _load_group_config.assert_called_once_with()
        _get_image_distgit_branch.assert_called_once_with(group_config)
        _build_plashets.assert_called_once_with(timestamp, 8, group_config)
        _rebase_image.assert_called_once_with(f"{timestamp}.p?")
        open.assert_called_once_with(Path("/path/to/plashet-b/rebuild.repo"), "w")
        _generate_repo_file_for_image.assert_called_once_with(open.return_value.__enter__.return_value, "plashet-a", "http://example.com/plashet-b")
        _copy_plashet_out_to_remote.assert_any_call(8, Path("/path/to/plashet-a"))
        _copy_plashet_out_to_remote.assert_any_call(8, Path("/path/to/plashet-b"))
        _build_image.assert_called_once_with("http://example.com/plashet-b/rebuild.repo")
        _generate_example_schema.assert_called_once_with(_build_image.return_value)

    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._copy_plashet_out_to_remote")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._generate_repo_file_for_rhcos")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._build_plashets")
    @patch("pyartcd.pipelines.rebuild.RebuildPipeline._load_group_config")
    @patch("builtins.open")
    @patch("pyartcd.pipelines.rebuild.datetime")
    def test_run_rhcos(self, mock_datetime: Mock, open: Mock, _load_group_config: Mock, _build_plashets: Mock,
                       _generate_repo_file_for_rhcos: Mock, _copy_plashet_out_to_remote: Mock):
        mock_datetime.utcnow.return_value = datetime(2021, 7, 16, 0, 0, 0, 0, tzinfo=timezone.utc)
        timestamp = mock_datetime.utcnow.return_value.strftime("%Y%m%d%H%M")
        runtime = MagicMock(dry_run=False)
        pipeline = RebuildPipeline(runtime, group="openshift-4.9", assembly="art0001", type=RebuildType.RHCOS, dg_key=None)
        group_config = {
            "arches": ["x86_64", "s390x"],
            "signing_advisory": 12345,
        }
        _load_group_config.return_value = group_config
        _build_plashets.return_value = (Path("/path/to/plashet-a"), "http://example.com/plashet-a", Path("/path/to/plashet-b"), "http://example.com/plashet-b")
        get_event_loop().run_until_complete(pipeline.run())
        _load_group_config.assert_called_once_with()
        _build_plashets.assert_called_once_with(timestamp, 8, group_config)
        open.assert_called_once_with(Path("/path/to/plashet-b/rebuild.repo"), "w")
        _generate_repo_file_for_rhcos.assert_called_once_with(open.return_value.__enter__.return_value, "http://example.com/plashet-a", "http://example.com/plashet-b")
        _copy_plashet_out_to_remote.assert_any_call(8, Path("/path/to/plashet-a"))
        _copy_plashet_out_to_remote.assert_any_call(8, Path("/path/to/plashet-b"))

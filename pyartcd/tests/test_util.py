from asyncio import get_event_loop
from unittest.case import TestCase

from mock import ANY, patch, Mock
from pyartcd import util


class TestUtil(TestCase):
    def test_isolate_el_version_in_release(self):
        self.assertEqual(util.isolate_el_version_in_release('1.2.3-y.p.p1.assembly.4.9.99.el7'), 7)
        self.assertEqual(util.isolate_el_version_in_release('1.2.3-y.p.p1.assembly.4.9.el7'), 7)
        self.assertEqual(util.isolate_el_version_in_release('1.2.3-y.p.p1.assembly.art12398.el199'), 199)
        self.assertEqual(util.isolate_el_version_in_release('1.2.3-y.p.p1.assembly.art12398'), None)
        self.assertEqual(util.isolate_el_version_in_release('1.2.3-y.p.p1.assembly.4.7.e.8'), None)

    def test_isolate_el_version_in_branch(self):
        self.assertEqual(util.isolate_el_version_in_branch('rhaos-4.9-rhel-7-candidate'), 7)
        self.assertEqual(util.isolate_el_version_in_branch('rhaos-4.9-rhel-7-hotfix'), 7)
        self.assertEqual(util.isolate_el_version_in_branch('rhaos-4.9-rhel-7'), 7)
        self.assertEqual(util.isolate_el_version_in_branch('rhaos-4.9-rhel-777'), 777)
        self.assertEqual(util.isolate_el_version_in_branch('rhaos-4.9'), None)

    @patch("pyartcd.exectools.cmd_gather_async")
    def test_load_group_config(self, cmd_gather_async: Mock):
        group_config_content = """
        key: "value"
        """
        cmd_gather_async.return_value = (0, group_config_content, "")
        actual = get_event_loop().run_until_complete(util.load_group_config("openshift-4.9", "art0001"))
        cmd_gather_async.assert_called_once_with(["doozer", "--group", "openshift-4.9", "--assembly", "art0001", "config:read-group", "--yaml"], stderr=None, env=ANY)
        self.assertEqual(actual["key"], "value")

    @patch("pyartcd.exectools.cmd_gather_async")
    def test_get_all_assembly_semvers_for_release(self, cmd_gather_async: Mock):
        releases_config = """
        "releases": {
            "4.9.1": {"assembly": {"type": "standard"}},
            "rc.0": {"assembly": {"type": "candidate"}},
            "art123": {"assembly": {"type": "custom"}},
            "fc.4": {"assembly": {"type": "candidate"}},
        }
        """
        cmd_gather_async.return_value = (0, releases_config, "")
        actual = get_event_loop().run_until_complete(util.get_all_assembly_semvers_for_release(4, 9, "path"))
        cmd_gather_async.assert_called_once()
        self.assertEqual(actual, ["4.9.1", "4.9.0-rc.0", "4.9.0-fc.4"])

    def test_sorted_semver(self):
        versions = ["4.9.1", "4.9.0-rc.0", "4.9.0-fc.4"]
        sorted_versions = ["4.9.0-fc.4", "4.9.0-rc.0", "4.9.1"]
        sorted_versions_reverse = ["4.9.1", "4.9.0-rc.0", "4.9.0-fc.4"]
        self.assertEqual(util.sorted_semver(versions), sorted_versions)
        self.assertEqual(util.sorted_semver(versions, reverse=True), sorted_versions_reverse)

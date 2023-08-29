from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, ANY, patch
from pyartcd import util


class TestUtil(IsolatedAsyncioTestCase):
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

    @patch("tempfile.mkdtemp")
    @patch("shutil.rmtree")
    @patch("pyartcd.exectools.cmd_gather_async")
    async def test_load_group_config(self, cmd_gather_async: AsyncMock, *_):
        group_config_content = """
        key: "value"
        """
        cmd_gather_async.return_value = (0, group_config_content, "")
        actual = await util.load_group_config("openshift-4.9", "art0001")
        self.assertEqual(actual["key"], "value")

    def test_dockerfile_url_for(self):
        # HTTPS url
        url = util.dockerfile_url_for(
            url='https://github.com/openshift/ironic-image',
            branch='release-4.13',
            sub_path='scripts'
        )
        self.assertEqual(url, 'https///github.com/openshift/ironic-image/blob/release-4.13/scripts')

        # Empty subpath
        url = util.dockerfile_url_for(
            url='https://github.com/openshift/ironic-image',
            branch='release-4.13',
            sub_path=''
        )
        self.assertEqual(url, 'https///github.com/openshift/ironic-image/blob/release-4.13/')

        # Empty url
        url = util.dockerfile_url_for(
            url='',
            branch='release-4.13',
            sub_path=''
        )
        self.assertEqual(url, '')

        # Empty branch
        url = util.dockerfile_url_for(
            url='https://github.com/openshift/ironic-image',
            branch='',
            sub_path='scripts'
        )
        self.assertEqual(url, '')

        # SSH remote
        url = util.dockerfile_url_for(
            url='git@github.com:openshift/ironic-image.git',
            branch='release-4.13',
            sub_path='scripts'
        )
        self.assertEqual(url, 'https///github.com/openshift/ironic-image/blob/release-4.13/scripts')

        # SSH remote, empty subpath
        url = util.dockerfile_url_for(
            url='git@github.com:openshift/ironic-image.git',
            branch='release-4.13',
            sub_path=''
        )
        self.assertEqual(url, 'https///github.com/openshift/ironic-image/blob/release-4.13/')

    @patch("pyartcd.exectools.cmd_gather_async")
    async def test_get_freeze_automation(self, cmd_gather_async: AsyncMock):
        cmd_gather_async.return_value = (0, '', '')

        await util.get_freeze_automation(
            version='4.15'
        )
        cmd_gather_async.assert_awaited_once_with(
            ['doozer', '', '--assembly=stream', '--data-path=https://github.com/openshift-eng/ocp-build-data',
             '--group=openshift-4.15', 'config:read-group', '--default=no', 'freeze_automation'])

        cmd_gather_async.reset_mock()
        await util.get_freeze_automation(
            version='4.15',
            doozer_data_path='https://github.com/random-fork/ocp-build-data',
            doozer_working='doozer_working',
            doozer_data_gitref='random-branch'
        )
        cmd_gather_async.assert_awaited_once_with(
            ['doozer', '--working-dir=doozer_working', '--assembly=stream',
             '--data-path=https://github.com/random-fork/ocp-build-data',
             '--group=openshift-4.15@random-branch', 'config:read-group', '--default=no', 'freeze_automation'])

    @patch("pyartcd.util.get_weekday")
    @patch("pyartcd.util.is_manual_build")
    @patch("pyartcd.util.get_freeze_automation")
    async def test_is_build_permitted(self, get_freeze_automation_mock: AsyncMock, is_manual_build_mock, weekday_mock):
        # Automation is frozen
        get_freeze_automation_mock.return_value = 'yes'
        res = await util.is_build_permitted(version='4.15')
        self.assertFalse(res)

        get_freeze_automation_mock.return_value = 'True'
        res = await util.is_build_permitted(version='4.15')
        self.assertFalse(res)

        # Scheduled automation is frozen, scheduled build
        get_freeze_automation_mock.return_value = 'scheduled'
        is_manual_build_mock.return_value = False
        res = await util.is_build_permitted(version='4.15')
        self.assertFalse(res)

        # Scheduled automation is frozen, manual build
        is_manual_build_mock.return_value = True
        res = await util.is_build_permitted(version='4.15')
        self.assertTrue(res)

        # Automation frozen during weekdays; scheduled builds
        get_freeze_automation_mock.return_value = 'weekdays'
        is_manual_build_mock.return_value = False
        weekday_mock.return_value = 'Sunday'
        res = await util.is_build_permitted(version='4.15')
        self.assertTrue(res)
        weekday_mock.return_value = 'Monday'
        res = await util.is_build_permitted(version='4.15')
        self.assertFalse(res)

        # Unknown value for 'freeze_automation'
        get_freeze_automation_mock.return_value = 'unknown'
        res = await util.is_build_permitted(version='4.15')
        self.assertTrue(res)

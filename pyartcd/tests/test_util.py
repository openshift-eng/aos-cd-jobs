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

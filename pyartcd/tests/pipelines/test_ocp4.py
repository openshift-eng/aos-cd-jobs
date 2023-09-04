import asyncio
import os
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from pyartcd import constants
from pyartcd.pipelines import ocp4


class TestInitialBuildPlan(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocp4: ocp4.Ocp4Pipeline = self.default_ocp4_pipeline()

    def setUp(self) -> None:
        self.ocp4 = self.default_ocp4_pipeline()

    @staticmethod
    def default_ocp4_pipeline() -> ocp4.Ocp4Pipeline:
        return ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.14',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initial_build_plan(self, _):
        await self.ocp4._initialize_build_plan()

        self.assertEqual(self.ocp4.build_plan.active_image_count, 219)
        self.assertEqual(self.ocp4.build_plan.dry_run, False)
        self.assertEqual(self.ocp4.build_plan.pin_builds, False)
        self.assertEqual(self.ocp4.build_plan.build_rpms, True)
        self.assertEqual(self.ocp4.build_plan.rpms_included, [])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, [])
        self.assertEqual(self.ocp4.build_plan.build_images, True)
        self.assertEqual(self.ocp4.build_plan.images_included, [])
        self.assertEqual(self.ocp4.build_plan.images_excluded, [])

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initial_build_plan_no_images_no_rpms(self, _):
        self.ocp4.build_rpms = 'none'
        self.ocp4.build_images = 'none'

        await self.ocp4._initialize_build_plan()

        self.assertEqual(self.ocp4.build_plan.build_rpms, False)
        self.assertEqual(self.ocp4.build_plan.build_images, False)

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initial_build_plan_include_rpm_list(self, _):
        # RPM list not allowed when build_rpms == "all"
        self.ocp4.rpm_list = 'rpm1, rpm2'
        with self.assertRaises(AssertionError):
            await self.ocp4._initialize_build_plan()

        # RPM list allowed when build_rpms == "only"
        self.ocp4.build_rpms = 'only'
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.rpms_included, ['rpm1', 'rpm2'])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, [])

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initial_build_plan_exclude_rpm_list(self, _):
        # RPM list not allowed when build_rpms == "all"
        self.ocp4.rpm_list = 'rpm1, rpm2'
        with self.assertRaises(AssertionError):
            await self.ocp4._initialize_build_plan()

        # RPM list allowed when build_rpms == "except"
        self.ocp4.build_rpms = 'except'
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.rpms_included, [])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, ['rpm1', 'rpm2'])

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initial_build_plan_include_image_list(self, _):
        # Image list not allowed when build_images == "all"
        self.ocp4.image_list = 'image1, image2'
        with self.assertRaises(AssertionError):
            await self.ocp4._initialize_build_plan()

        # Image list allowed when build_images == "only"
        self.ocp4.build_images = 'only'
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.images_included, ['image1', 'image2'])
        self.assertEqual(self.ocp4.build_plan.images_excluded, [])

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initial_build_plan_exclude_image_list(self, _):
        # Image list not allowed when build_images == "all"
        self.ocp4.image_list = 'image1, image2'
        with self.assertRaises(AssertionError):
            await self.ocp4._initialize_build_plan()

        # Image list allowed when build_images == "except"
        self.ocp4.build_images = 'except'
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.images_included, [])
        self.assertEqual(self.ocp4.build_plan.images_excluded, ['image1', 'image2'])


class TestPlannedBuilds(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocp4: ocp4.Ocp4Pipeline = self.default_ocp4_pipeline()

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    def setUp(self, *_) -> None:
        self.ocp4 = self.default_ocp4_pipeline()
        asyncio.get_event_loop().run_until_complete(self.ocp4._initialize_build_plan())

    @staticmethod
    def default_ocp4_pipeline() -> ocp4.Ocp4Pipeline:
        return ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.14',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._get_changes", return_value={})
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._check_changed_child_images")
    async def test_no_changes(self, *_):
        self.assertEqual(self.ocp4.build_plan.build_rpms, True)
        self.assertEqual(self.ocp4.build_plan.build_images, True)

        # After running _plan_builds(), build rpms/images flags shall be reset to False
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.build_rpms, False)
        self.assertEqual(self.ocp4.build_plan.build_images, False)

    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_check_changed_rpms(self, *_):
        await self.ocp4._initialize_build_plan()
        self.assertTrue(self.ocp4.build_plan.build_rpms)

        # Do not build RPMs, RPMs changed
        self.ocp4.build_plan.build_rpms = False
        changes = {'rpms': ['rpm1', 'rpm2']}
        self.ocp4._check_changed_rpms(changes)
        self.assertFalse(self.ocp4.build_plan.build_rpms)

        # Build RPMs, RPMs changed
        await self.ocp4._initialize_build_plan()
        self.assertTrue(self.ocp4.build_plan.build_rpms)
        changes = {'rpms': ['rpm1', 'rpm2']}
        self.ocp4._check_changed_rpms(changes)
        self.assertTrue(self.ocp4.build_plan.build_rpms)
        self.assertEqual(self.ocp4.build_plan.rpms_included, ['rpm1', 'rpm2'])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, [])

        # Build RPMs, no RPMs changed
        changes = {'rpms': []}
        self.ocp4._check_changed_rpms(changes)
        self.assertFalse(self.ocp4.build_plan.build_rpms)

    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._get_changes", return_value={'rpms': ['rpm1', 'rpm2']})
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._check_changed_child_images")
    async def test_changed_rpms(self, *_):
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.build_rpms, True)
        self.assertEqual(self.ocp4.build_plan.rpms_included, ['rpm1', 'rpm2'])
        self.assertEqual(self.ocp4.build_plan.build_images, False)

        # When source changes matter, rpms included/excluded get overridden with actual changed RPMs
        self.ocp4.build_plan.build_rpms = 'only'
        self.ocp4.build_plan.rpm_list = ['rpmX', 'rpmY']
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.rpms_included, ['rpm1', 'rpm2'])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, [])

        self.ocp4.build_plan.build_rpms = 'except'
        self.ocp4.build_plan.rpm_list = ['rpmX', 'rpmY']
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.rpms_included, ['rpm1', 'rpm2'])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, [])

    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._get_changes", return_value={'images': ['image1', 'image2']})
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._check_changed_child_images", return_value=[])
    async def test_changed_images(self, *_):
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.build_rpms, False)
        self.assertEqual(self.ocp4.build_plan.build_images, True)
        self.assertEqual(self.ocp4.build_plan.images_included, ['image1', 'image2'])

    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._get_changes")
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._check_changed_child_images")
    async def test_changed_child_images(self, check_changed_child_images_mock, get_changes_mock, *_):
        get_changes_mock.return_value = {'images': ['image1', 'image2']}
        check_changed_child_images_mock.return_value = ['image3', 'image4']
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.build_rpms, False)
        self.assertEqual(self.ocp4.build_plan.build_images, True)
        self.assertEqual(self.ocp4.build_plan.images_included, ['image1', 'image2', 'image3', 'image4'])

        get_changes_mock.return_value = {'images': ['image1', 'image2']}
        check_changed_child_images_mock.return_value = ['image1', 'image2']
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.build_rpms, False)
        self.assertEqual(self.ocp4.build_plan.build_images, True)
        self.assertEqual(self.ocp4.build_plan.images_included, ['image1', 'image2'])

        get_changes_mock.return_value = {}
        check_changed_child_images_mock.return_value = ['image3', 'image4']
        await self.ocp4._plan_builds()
        self.assertEqual(self.ocp4.build_plan.build_rpms, False)
        self.assertEqual(self.ocp4.build_plan.build_images, False)

    async def test_gather_children(self, *_):
        show_tree_output = {'image1': {'child1': {'child2': {}}}}
        changed_images = ['image1', 'image2']
        children = []
        self.ocp4._gather_children(
            all_images=children,
            data=show_tree_output,
            initial=changed_images,
            gather=False
        )
        self.assertEqual(children, ['image1', 'child1', 'child2'])

        show_tree_output = {'image1': {'child1': {'child2': {}}}}
        changed_images = ['image2']
        children = []
        self.ocp4._gather_children(
            all_images=children,
            data=show_tree_output,
            initial=changed_images,
            gather=False
        )
        self.assertEqual(children, [])

        show_tree_output = {}
        changed_images = ['image2']
        children = []
        self.ocp4._gather_children(
            all_images=children,
            data=show_tree_output,
            initial=changed_images,
            gather=False
        )
        self.assertEqual(children, [])

    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.exectools.cmd_gather_async")
    async def test_check_changed_child_images(self, cmd_gather_mock, _):
        cmd_gather_mock.return_value = (0, 'image1:\n  child1:\n    child2: {}\nimage2:\n  child3: {}', '')
        changes = {'images': ['image1']}
        changed_children = await self.ocp4._check_changed_child_images(changes)
        self.assertEqual(sorted(changed_children), ['child1', 'child2'])

        cmd_gather_mock.return_value = (0, 'image1:\n  child1:\n    child2: {}\nimage2:\n  child3: {}', '')
        changes = {'images': ['image2']}
        changed_children = await self.ocp4._check_changed_child_images(changes)
        self.assertEqual(sorted(changed_children), ['child3'])

        cmd_gather_mock.return_value = (0, 'image1:\n  child1:\n    child2: {}\nimage2:\n  child3: {}', '')
        changes = {'images': ['image1', 'image2']}
        changed_children = await self.ocp4._check_changed_child_images(changes)
        self.assertEqual(sorted(changed_children), ['child1', 'child2', 'child3'])

        cmd_gather_mock.return_value = (0, 'image1:\n  image2:\n    child1: {}', '')
        changes = {'images': ['image1', 'image2']}
        changed_children = await self.ocp4._check_changed_child_images(changes)
        self.assertEqual(sorted(changed_children), ['child1'])

        cmd_gather_mock.return_value = (0, 'image1:\n  child1:\n    child2: {}\nimage2:\n  child3: {}', '')
        changes = {'images': []}
        changed_children = await self.ocp4._check_changed_child_images(changes)
        self.assertEqual(sorted(changed_children), [])

        cmd_gather_mock.return_value = (0, 'image1:\n  child1:\n    child2: {}\nimage2:\n  child3: {}', '')
        changes = {}
        changed_children = await self.ocp4._check_changed_child_images(changes)
        self.assertEqual(sorted(changed_children), [])

    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.exectools.cmd_gather_async", autospec=True,
           return_value=(0, 'image1:\n  child1:\n    child2: {}\nimage2:\n  child3: {}', ''))
    async def test_check_changed_images(self, *_):
        # Do not build images, images changed
        self.ocp4.build_plan.build_images = False
        changes = {'images': ['image1', 'image2']}
        await self.ocp4._check_changed_images(changes)
        self.assertFalse(self.ocp4.build_plan.build_images)

        # Build images, no image changed
        self.ocp4.build_plan.build_images = True
        changes = {}
        await self.ocp4._check_changed_images(changes)
        self.assertFalse(self.ocp4.build_plan.build_images)

        # Build images, images changed
        self.ocp4.build_plan.build_images = True
        changes = {'images': ['image1', 'image2']}
        await self.ocp4._check_changed_images(changes)
        self.assertEqual(self.ocp4.build_plan.images_excluded, [])
        self.assertEqual(self.ocp4.build_plan.images_included, ['image1', 'image2', 'child1', 'child2', 'child3'])


class TestInitialize(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocp4: ocp4.Ocp4Pipeline = self.default_ocp4_pipeline()

    @staticmethod
    def default_ocp4_pipeline() -> ocp4.Ocp4Pipeline:
        return ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.14',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

    def setUp(self) -> None:
        self.ocp4 = self.default_ocp4_pipeline()

    @patch("pyartcd.exectools.cmd_gather_async")
    async def test_check_assembly(self, cmd_gather_async_mock):
        # Assemblies enabled, assembly = 'stream': no exception
        cmd_gather_async_mock.return_value = (0, 'True', '')
        self.ocp4.assembly = 'stream'
        await self.ocp4._check_assembly()

        # Assemblies enabled, assembly != 'stream': no exception
        cmd_gather_async_mock.return_value = (0, 'True', '')
        self.ocp4.assembly = 'art123456'
        await self.ocp4._check_assembly()

        # Assemblies disabled, assembly = 'stream': no exception
        cmd_gather_async_mock.return_value = (0, 'Falsae', '')
        self.ocp4.assembly = 'stream'
        await self.ocp4._check_assembly()

        # Assemblies disabled, assembly != 'stream': RuntimeError exception is raised
        cmd_gather_async_mock.return_value = (0, 'False', '')
        self.ocp4.assembly = 'art123456'
        with self.assertRaises(RuntimeError):
            await self.ocp4._check_assembly()

    @patch("pyartcd.exectools.cmd_gather_async", return_value=(0, 'rhaos-4.12-rhel-8', ''))
    @patch("pyartcd.jenkins.update_title")
    async def test_initialize_version(self, *_):

        # Mock datetime.now()
        class MockedDatetime(datetime):
            @classmethod
            def now(cls, *args, **kwargs):
                return datetime(2100, month=12, day=31, hour=11, minute=12)
        ocp4.util.datetime = MockedDatetime

        # Initial values
        self.assertEqual(self.ocp4.version.stream, '4.14')
        self.assertEqual(self.ocp4.version.branch, '')
        self.assertEqual(self.ocp4.version.release, '')
        self.assertEqual(self.ocp4.version.major, 0)
        self.assertEqual(self.ocp4.version.minor, 0)

        # After version initialization
        await self.ocp4._initialize_version()
        self.assertEqual(self.ocp4.version.branch, 'rhaos-4.12-rhel-8')
        self.assertEqual(self.ocp4.version.release, '210012311112.p?')
        self.assertEqual(self.ocp4.version.major, 4)
        self.assertEqual(self.ocp4.version.minor, 14)

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initialize_build_plan_default(self, *_):
        # Default ocp4 pipeline
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.active_image_count, 219)
        self.assertEqual(self.ocp4.build_plan.build_images, True)
        self.assertEqual(self.ocp4.build_plan.build_rpms, True)

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initialize_build_plan_no_images_no_rpms(self, *_):
        # No images, rpms
        self.ocp4.build_images = 'none'
        self.ocp4.build_rpms = 'none'
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.build_images, False)
        self.assertEqual(self.ocp4.build_plan.build_rpms, False)

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initialize_build_plan_include_images_rpms(self, *_):
        # Include images/rpms, empty lists
        self.ocp4.build_images = 'only'
        self.ocp4.build_rpms = 'only'
        self.ocp4.image_list = ''
        self.ocp4.rpm_list = ''
        with self.assertRaises(AssertionError):
            await self.ocp4._initialize_build_plan()

        # Include images/rpms, non-empty lists
        self.ocp4.image_list = 'image1 ,image2'
        self.ocp4.rpm_list = 'rpm1, rpm2'
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.build_images, True)
        self.assertEqual(self.ocp4.build_plan.build_rpms, True)
        self.assertEqual(self.ocp4.build_plan.images_included, ['image1', 'image2'])
        self.assertEqual(self.ocp4.build_plan.rpms_included, ['rpm1', 'rpm2'])
        self.assertEqual(self.ocp4.build_plan.images_excluded, [])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, [])

    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "219 images", ""))
    async def test_initialize_build_plan_exclude_images_rpms(self, *_):
        # Exclude images/rpms, empty lists
        self.ocp4.build_images = 'except'
        self.ocp4.build_rpms = 'except'
        self.ocp4.image_list = ''
        self.ocp4.rpm_list = ''
        with self.assertRaises(AssertionError):
            await self.ocp4._initialize_build_plan()

        # Exclude images/rpms, non-empty lists
        self.ocp4.image_list = 'image1 ,image2'
        self.ocp4.rpm_list = 'rpm1, rpm2'
        await self.ocp4._initialize_build_plan()
        self.assertEqual(self.ocp4.build_plan.build_images, True)
        self.assertEqual(self.ocp4.build_plan.build_rpms, True)
        self.assertEqual(self.ocp4.build_plan.images_included, [])
        self.assertEqual(self.ocp4.build_plan.rpms_included, [])
        self.assertEqual(self.ocp4.build_plan.images_excluded, ['image1', 'image2'])
        self.assertEqual(self.ocp4.build_plan.rpms_excluded, ['rpm1', 'rpm2'])


class TestBuilds(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocp4: ocp4.Ocp4Pipeline = self.default_ocp4_pipeline()

    @staticmethod
    @patch("os.path.abspath", return_value='doozer_working')
    def default_ocp4_pipeline(*_) -> ocp4.Ocp4Pipeline:
        pipeline = ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.13',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )
        pipeline._doozer_working = 'doozer_working'
        pipeline.build_plan.active_image_count = 5
        return pipeline

    @patch("shutil.rmtree")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.util.default_release_suffix", return_value="2100123111.p?")
    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "rhaos-4.13-rhel-8", ""))
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_build_rpms(self, cmd_assert_mock: AsyncMock, *_):
        await self.ocp4._initialize_version()

        # no RPMs
        self.assertFalse(self.ocp4.build_plan.build_rpms)
        await self.ocp4._rebase_and_build_rpms()
        cmd_assert_mock.assert_not_awaited()

        # Include RPMs
        cmd_assert_mock.reset_mock()
        self.ocp4.build_plan.build_rpms = True
        self.ocp4.build_plan.rpms_included = ['rpm1']
        self.ocp4.build_plan.rpms_excluded = []
        await self.ocp4._rebase_and_build_rpms()
        cmd_assert_mock.assert_awaited_once_with(
            [
                'doozer', '--assembly=stream', '--working-dir=doozer_working',
                '--data-path=https://github.com/openshift-eng/ocp-build-data', '--group=openshift-4.13',
                '--latest-parent-version', '--rpms', 'rpm1', 'rpms:rebase-and-build', '--version=4.13',
                '--release=2100123111.p?'
            ]
        )

        # Exclude RPMs
        cmd_assert_mock.reset_mock()
        self.ocp4.build_plan.build_rpms = True
        self.ocp4.build_plan.rpms_included = []
        self.ocp4.build_plan.rpms_excluded = ['rpm1']
        await self.ocp4._rebase_and_build_rpms()
        cmd_assert_mock.assert_awaited_once_with(
            [
                'doozer', '--assembly=stream', '--working-dir=doozer_working',
                '--data-path=https://github.com/openshift-eng/ocp-build-data', '--group=openshift-4.13',
                '--latest-parent-version', "--rpms=", '--exclude', 'rpm1', 'rpms:rebase-and-build',
                '--version=4.13', '--release=2100123111.p?'
            ]
        )

    @patch("shutil.rmtree")
    @patch("builtins.open")
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.jenkins.start_scan_osh")
    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.util.default_release_suffix", return_value="2100123111.p?")
    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "rhaos-4.13-rhel-8", ""))
    @patch("pyartcd.util.load_group_config", return_value={'software_lifecycle': {'phase': 'release'}})
    @patch("pyartcd.oc.registry_login")
    @patch("pyartcd.record.parse_record_log")
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_build_and_rebase_images(self, cmd_assert_mock: AsyncMock, parse_record_log_mock, registry_login_mock, *_):
        parse_record_log_mock.return_value = {}
        await self.ocp4._initialize_version()

        # no images
        self.assertFalse(self.ocp4.build_plan.build_images)
        await self.ocp4._rebase_and_build_images()
        cmd_assert_mock.assert_not_awaited()

        # Include images
        cmd_assert_mock.reset_mock()
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = ['image1', 'image2']
        self.ocp4.build_plan.images_excluded = []
        await self.ocp4._build_images()
        cmd_assert_mock.assert_awaited_once_with(
            [
                'doozer', '--assembly=stream', '--working-dir=doozer_working',
                '--data-path=https://github.com/openshift-eng/ocp-build-data', '--group=openshift-4.13',
                '--latest-parent-version', '--images', 'image1,image2', 'images:build', '--repo-type', 'signed'
            ]
        )
        registry_login_mock.assert_not_awaited()

        # Exclude images
        cmd_assert_mock.reset_mock()
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = []
        self.ocp4.build_plan.images_excluded = ['image1', 'image2', 'image3']
        await self.ocp4._build_images()
        cmd_assert_mock.assert_awaited_once_with(
            [
                'doozer', '--assembly=stream', '--working-dir=doozer_working',
                '--data-path=https://github.com/openshift-eng/ocp-build-data', '--group=openshift-4.13',
                '--latest-parent-version', "--images=", '--exclude', 'image1,image2,image3', 'images:build',
                '--repo-type', 'signed'
            ]
        )
        registry_login_mock.assert_not_awaited()

        # Dry run
        cmd_assert_mock.reset_mock()
        self.ocp4.runtime.dry_run = True
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = ['image1', 'image2']
        self.ocp4.build_plan.images_excluded = []
        await self.ocp4._build_images()
        cmd_assert_mock.assert_not_awaited()
        registry_login_mock.assert_not_awaited()

        # ApiServer rebuilt
        cmd_assert_mock.reset_mock()
        parse_record_log_mock.return_value = {'build': [{'distgit': 'ose-openshift-apiserver', 'status': '0', 'nvrs': 'bogus'}]}
        self.ocp4.runtime.dry_run = False
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = ['image1', 'image2']
        self.ocp4.build_plan.images_excluded = []
        await self.ocp4._build_images()
        registry_login_mock.assert_awaited_once()
        cmd_assert_mock.assert_awaited_with(
            [
                'doozer', '--assembly=stream', '--working-dir=doozer_working',
                '--data-path=https://github.com/openshift-eng/ocp-build-data',
                '--group=openshift-4.13', 'images:streams', 'mirror'
            ]
        )

    @patch("shutil.rmtree")
    @patch("builtins.open")
    @patch("pyartcd.record.parse_record_log", return_value={})
    @patch("pyartcd.jenkins.update_title")
    @patch("pyartcd.jenkins.update_description")
    @patch("pyartcd.util.default_release_suffix", return_value="2100123111.p?")
    @patch("pyartcd.exectools.cmd_gather_async", autospec=True, return_value=(0, "rhaos-4.13-rhel-8", ""))
    @patch("pyartcd.util.load_group_config", return_value={'software_lifecycle': {'phase': 'release'}})
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_mass_rebuild(self, cmd_assert_async_mock: AsyncMock, *_):
        # Build plan includes more than half of the images: it's a mass rebuild
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = ['image1', 'image2', 'image3']
        self.ocp4.build_plan.images_excluded = []
        self.ocp4.check_mass_rebuild()
        self.assertTrue(self.ocp4.mass_rebuild)

        # Build plan includes less than half of the images: not a mass rebuild
        cmd_assert_async_mock.reset_mock()
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = ['image1', 'image2']
        self.ocp4.build_plan.images_excluded = []
        self.ocp4.check_mass_rebuild()
        self.assertFalse(self.ocp4.mass_rebuild)

        # Build plan excludes less than half of the images: it's a mass rebuild
        cmd_assert_async_mock.reset_mock()
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = []
        self.ocp4.build_plan.images_excluded = ['image1']
        self.ocp4.check_mass_rebuild()
        self.assertTrue(self.ocp4.mass_rebuild)

        # Build plan excludes more than half of the images: not a mass rebuild
        cmd_assert_async_mock.reset_mock()
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = []
        self.ocp4.build_plan.images_excluded = ['image1', 'image2', 'image3']
        self.ocp4.check_mass_rebuild()
        self.assertFalse(self.ocp4.mass_rebuild)

        # Build plan rebuilds everything: it's a mass rebuild
        cmd_assert_async_mock.reset_mock()
        self.ocp4.build_plan.build_images = True
        self.ocp4.build_plan.images_included = []
        self.ocp4.build_plan.images_excluded = []
        self.ocp4.check_mass_rebuild()
        self.assertTrue(self.ocp4.mass_rebuild)


class TestBuildCompose(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocp4: ocp4.Ocp4Pipeline = self.default_ocp4_pipeline()

    @staticmethod
    @patch("os.path.abspath", return_value='doozer_working')
    def default_ocp4_pipeline(*_) -> ocp4.Ocp4Pipeline:
        return ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.13',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

    @patch("pyartcd.util.get_freeze_automation", return_value="False")
    async def test_automation_freeze_false(self, *_):
        # If automation is not frozen, compose build is permitted
        res = await self.ocp4._is_compose_build_permitted()
        self.assertEqual(res, True)

    @patch("pyartcd.util.get_freeze_automation", return_value="weekdays")
    async def test_automation_freeze_weekdays(self, *_):
        # If automation is not frozen, compose build is permitted
        res = await self.ocp4._is_compose_build_permitted()
        self.assertEqual(res, True)

    @patch("pyartcd.util.get_freeze_automation", return_value="yes")
    async def test_automation_freeze_yes(self, *_):
        # If automation is frozen, compose build is permitted
        res = await self.ocp4._is_compose_build_permitted()
        self.assertEqual(res, False)

    @patch("pyartcd.util.get_freeze_automation", return_value="True")
    async def test_automation_freeze_true(self, *_):
        # If automation is frozen, compose build is permitted
        res = await self.ocp4._is_compose_build_permitted()
        self.assertEqual(res, False)

    @patch("pyartcd.util.get_freeze_automation", return_value="scheduled")
    @patch("pyartcd.util.is_manual_build", return_value=True)
    async def test_automation_freeze_scheduled(self, *_):
        # If automation is scheduled, build compose only if there are RPMs in the build plan
        self.ocp4._slack_client.say = AsyncMock()
        self.ocp4.build_plan.build_rpms = True
        res = await self.ocp4._is_compose_build_permitted()
        self.assertEqual(res, True)
        self.ocp4._slack_client.say.assert_awaited_once()

    @patch("pyartcd.locks.LockManager.from_lock", return_value=AsyncMock)
    @patch("pyartcd.plashets.build_plashets", return_value=AsyncMock)
    @patch("pyartcd.jenkins.start_sync_for_ci")
    @patch("pyartcd.jenkins.start_rhcos")
    async def test_build_compose(self, mocked_rhcos, mocked_sync_for_ci, mocked_build_plashets, mocked_lm):
        mocked_cm = AsyncMock()
        mocked_cm.__aenter__ = AsyncMock()
        mocked_cm.__aexit__ = AsyncMock()

        mocked_lm.return_value = AsyncMock()
        mocked_lm.return_value.lock.return_value = mocked_cm

        mocked_build_plashets.return_value = {}

        # Build not permitted
        self.ocp4._is_compose_build_permitted = AsyncMock(return_value=False)
        await self.ocp4._build_compose()
        mocked_build_plashets.assert_not_awaited()
        mocked_rhcos.assert_not_called()
        mocked_sync_for_ci.assert_not_called()

        # Build permitted, assembly != 'stream'
        mocked_build_plashets.reset_mock()
        mocked_rhcos.reset_mock()
        mocked_sync_for_ci.reset_mock()
        self.ocp4._is_compose_build_permitted = AsyncMock(return_value=True)
        self.ocp4.assembly = 'test'
        await self.ocp4._build_compose()
        mocked_build_plashets.assert_awaited_once()
        mocked_rhcos.assert_not_called()
        mocked_sync_for_ci.assert_not_called()

        # Build permitted, assembly = 'stream'
        mocked_build_plashets.reset_mock()
        mocked_rhcos.reset_mock()
        mocked_sync_for_ci.reset_mock()
        self.ocp4._is_compose_build_permitted = AsyncMock(return_value=True)
        self.ocp4.assembly = 'stream'
        await self.ocp4._build_compose()
        mocked_build_plashets.assert_awaited_once()
        mocked_rhcos.assert_called_once_with(build_version='4.13', new_build=False)
        mocked_sync_for_ci.assert_called_once_with(
            version='4.13', block_until_building=False)
        self.assertEqual(self.ocp4.rpm_mirror.local_plashet_path, '')
        self.assertEqual(self.ocp4.rpm_mirror.plashet_dir_name, '')

        # rhel7 plashet built
        mocked_build_plashets.reset_mock()
        mocked_build_plashets.return_value = {
            "rhel-8-server-ose-rpms": {
                "plashetDirName": "2023053008",
                "localPlashetPath": "plashet-working/plashets/4.7/stream/el8/2023-05/2023053008"
            },
            "rhel-server-ose-rpms": {
                "plashetDirName": "2023053008",
                "localPlashetPath": "plashet-working/plashets/4.7/stream/el7/2023-05/2023053008"
            }
        }
        await self.ocp4._build_compose()
        self.assertEqual(
            self.ocp4.rpm_mirror.local_plashet_path, 'plashet-working/plashets/4.7/stream/el7/2023-05/2023053008')
        self.assertEqual(
            self.ocp4.rpm_mirror.plashet_dir_name, '2023053008')


class TestUpdateDistgit(unittest.IsolatedAsyncioTestCase):
    @patch("pyartcd.pipelines.ocp4.Ocp4Pipeline._build_images")
    @patch("os.path.abspath", return_value='doozer_working')
    @patch("pyartcd.util.notify_dockerfile_reconciliations")
    @patch("pyartcd.util.notify_bz_info_missing")
    @patch("pyartcd.exectools.cmd_assert_async")
    async def test_update_distgit(self, cmd_assert_mock: AsyncMock, bz_info_missing_mock, reconciliations_mock, *_):
        pipeline = ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.13',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

        pipeline.version.release = '2099010109.p?'

        # No images to build
        pipeline.build_plan.build_images = False
        await pipeline._rebase_and_build_images()
        cmd_assert_mock.assert_not_awaited()
        bz_info_missing_mock.assert_not_called()
        reconciliations_mock.assert_not_called()

        # Images to build
        os.environ['BUILD_URL'] = 'build-url'
        cmd_assert_mock.reset_mock()
        bz_info_missing_mock.reset_mock()
        reconciliations_mock.reset_mock()
        pipeline.build_plan.build_images = True
        await pipeline._rebase_and_build_images()
        cmd_assert_mock.assert_awaited_once_with(
            [
                'doozer', '--assembly=stream', '--working-dir=doozer_working',
                '--data-path=https://github.com/openshift-eng/ocp-build-data', '--group=openshift-4.13',
                '--images=', 'images:rebase', '--version=v4.13', '--release=2099010109.p?',
                "--message='Updating Dockerfile version and release v4.13-2099010109.p?'", '--push',
                "--message='build-url'"
            ]
        )
        bz_info_missing_mock.assert_called_once()
        reconciliations_mock.assert_called_once()

        # Dry run
        cmd_assert_mock.reset_mock()
        bz_info_missing_mock.reset_mock()
        reconciliations_mock.reset_mock()
        pipeline.build_plan.build_images = True
        pipeline.runtime.dry_run = True
        await pipeline._rebase_and_build_images()
        cmd_assert_mock.assert_not_awaited()
        bz_info_missing_mock.assert_not_called()
        reconciliations_mock.assert_not_called()


class TestSyncImages(unittest.IsolatedAsyncioTestCase):
    @patch("os.path.abspath", return_value='doozer_working')
    @patch("builtins.open")
    @patch("pyartcd.record.parse_record_log", return_value={
        'build': [
            {'has_olm_bundle': '1', 'status': '0', 'nvrs': 'nvr1,nvr2'},
            {'has_olm_bundle': '0', 'status': '0', 'nvrs': 'nvr3'},
            {'has_olm_bundle': '1', 'status': '1', 'nvrs': 'nvr4'},
            {'has_olm_bundle': '1', 'status': '0', 'nvrs': ''},
            {'has_olm_bundle': '1', 'status': '0', 'nvrs': 'nvr5'},
        ]
    })
    @patch("pyartcd.util.sync_images")
    async def test_ocp4_sync_images(self, sync_images_mock: AsyncMock, *_):
        pipeline = ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.13',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

        # No images
        pipeline.build_plan.build_images = False
        await pipeline._sync_images()
        sync_images_mock.assert_not_awaited()

        # Built images
        pipeline.build_plan.build_images = True
        sync_images_mock.reset_mock()
        await pipeline._sync_images()
        sync_images_mock.assert_awaited_once_with(
            version='4.13', assembly='stream', operator_nvrs=['nvr1', 'nvr5'],
            doozer_data_path='https://github.com/openshift-eng/ocp-build-data',
            doozer_data_gitref=''
        )

    @patch("os.path.abspath", return_value='doozer_working')
    @patch("builtins.open")
    @patch("pyartcd.record.parse_record_log", return_value={
        'build': [
            {'has_olm_bundle': '1', 'status': '0', 'nvrs': 'nvr1,nvr2'},
            {'has_olm_bundle': '0', 'status': '0', 'nvrs': 'nvr3'},
            {'has_olm_bundle': '1', 'status': '1', 'nvrs': 'nvr4'},
            {'has_olm_bundle': '1', 'status': '0', 'nvrs': ''},
            {'has_olm_bundle': '1', 'status': '0', 'nvrs': 'nvr5'},
        ]
    })
    @patch("pyartcd.jenkins.start_olm_bundle")
    @patch("pyartcd.jenkins.start_build_sync")
    async def test_util_sync_images(self, build_sync_mock, olm_bundle_mock, *_):
        pipeline = ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.13',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

        # No images
        pipeline.build_plan.build_images = False
        await pipeline._sync_images()
        build_sync_mock.assert_not_called()
        olm_bundle_mock.assert_not_called()

        # Built images, assembly != 'stream
        pipeline.build_plan.build_images = True
        pipeline.assembly = 'test'
        build_sync_mock.reset_mock()
        olm_bundle_mock.reset_mock()
        await pipeline._sync_images()
        build_sync_mock.assert_not_called()
        olm_bundle_mock.assert_called_once()

        # Built images, assembly == 'stream
        pipeline.build_plan.build_images = True
        pipeline.assembly = 'stream'
        build_sync_mock.reset_mock()
        olm_bundle_mock.reset_mock()
        await pipeline._sync_images()
        build_sync_mock.assert_called_with(
            build_version='4.13', assembly='stream',
            doozer_data_path='https://github.com/openshift-eng/ocp-build-data',
            doozer_data_gitref=''
        )
        olm_bundle_mock.assert_called_with(
            build_version='4.13', assembly='stream', operator_nvrs=['nvr1', 'nvr5'],
            doozer_data_path='https://github.com/openshift-eng/ocp-build-data', doozer_data_gitref=''
        )


class TestMirrorRpms(unittest.IsolatedAsyncioTestCase):
    @patch("pyartcd.locks.LockManager.from_lock", return_value=AsyncMock)
    @patch("pyartcd.pipelines.ocp4.sync_repo_to_s3_mirror")
    async def test_sync_to_mirror(self, sync_mock: AsyncMock, mocked_lm):
        pipeline = ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='test',
            version='4.13',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

        # Mock lock manager
        mocked_cm = AsyncMock()
        mocked_cm.__aenter__ = AsyncMock()
        mocked_cm.__aexit__ = AsyncMock()

        mocked_lm.return_value = AsyncMock()
        mocked_lm.return_value.lock.return_value = mocked_cm

        # Assembly != stream: do not mirror
        await pipeline._mirror_rpms()
        sync_mock.assert_not_awaited()

        # No updated RPMs to mirror.
        self.assertEqual(pipeline.rpm_mirror.local_plashet_path, '')
        await pipeline._mirror_rpms()
        sync_mock.assert_not_awaited()

        # Mirror RPMs
        pipeline.assembly = 'stream'
        pipeline.rpm_mirror.local_plashet_path = '/some/path'
        await pipeline._mirror_rpms()
        sync_mock.assert_any_await(local_dir='/some/path', s3_path='/enterprise/enterprise-4.13/latest/', dry_run=False)
        sync_mock.assert_any_await(local_dir='/some/path', s3_path='/enterprise/all/4.13/latest/', dry_run=False)

        # Dry run
        sync_mock.reset_mock()
        pipeline.runtime.dry_run = True
        await pipeline._mirror_rpms()
        sync_mock.assert_any_await(local_dir='/some/path', s3_path='/enterprise/enterprise-4.13/latest/', dry_run=True)
        sync_mock.assert_any_await(local_dir='/some/path', s3_path='/enterprise/all/4.13/latest/', dry_run=True)


class TestUtils(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.ocp4 = self.default_ocp4_pipeline()

    @staticmethod
    def default_ocp4_pipeline() -> ocp4.Ocp4Pipeline:
        return ocp4.Ocp4Pipeline(
            runtime=MagicMock(dry_run=False),
            assembly='stream',
            version='4.14',
            data_path=constants.OCP_BUILD_DATA_URL,
            data_gitref='',
            pin_builds=False,
            build_rpms='all',
            rpm_list='',
            build_images='all',
            image_list='',
            skip_plashets=False,
            mail_list_failure=''
        )

    def test_include_exclude(self):
        # Include RPMs
        include_exclude = self.ocp4._include_exclude(
            kind='rpms',
            includes=['rpm1', 'rpm2'],
            excludes=[]
        )
        self.assertEqual(include_exclude, ['--latest-parent-version', '--rpms', 'rpm1,rpm2'])

        # Exclude RPMs
        include_exclude = self.ocp4._include_exclude(
            kind='rpms',
            includes=[],
            excludes=['rpm3', 'rpm4']
        )
        self.assertEqual(include_exclude, ['--latest-parent-version', "--rpms=", '--exclude', 'rpm3,rpm4'])

        # Include and exclude RPMs: includes take precedence
        include_exclude = self.ocp4._include_exclude(
            kind='rpms',
            includes=['rpm1', 'rpm2'],
            excludes=['rpm3', 'rpm4']
        )
        self.assertEqual(include_exclude, ['--latest-parent-version', '--rpms', 'rpm1,rpm2'])

        # Include images
        include_exclude = self.ocp4._include_exclude(
            kind='images',
            includes=['image1', 'image2'],
            excludes=[]
        )
        self.assertEqual(include_exclude, ['--latest-parent-version', '--images', 'image1,image2'])

        # Exclude images
        include_exclude = self.ocp4._include_exclude(
            kind='images',
            includes=[],
            excludes=['image3', 'image4']
        )
        self.assertEqual(include_exclude, ['--latest-parent-version', "--images=", '--exclude', 'image3,image4'])

        # Include and exclude images: includes take precedence
        include_exclude = self.ocp4._include_exclude(
            kind='images',
            includes=['image1', 'image2'],
            excludes=['image3', 'image4']
        )
        self.assertEqual(include_exclude, ['--latest-parent-version', '--images', 'image1,image2'])

        # Wrong kind: ValueError
        with self.assertRaises(ValueError):
            self.ocp4._include_exclude(
                kind='image',
                includes=['image1', 'image2'],
                excludes=[]
            )

    def test_display_tag_for(self):
        # One image included
        tag = self.ocp4._display_tag_for(['ironic'], 'image')
        self.assertEqual(tag, ' [ironic image]')

        # One RPM included
        tag = self.ocp4._display_tag_for(['python-ansible'], 'rpm')
        self.assertEqual(tag, ' [python-ansible rpm]')

        # More than one RPM included
        tag = self.ocp4._display_tag_for(['image1', 'image2'], 'image')
        self.assertEqual(tag, ' [2 images]')

        # More than one image included
        tag = self.ocp4._display_tag_for(['rpm1', 'rpm2'], 'rpm')
        self.assertEqual(tag, ' [2 rpms]')

        # One image excluded
        tag = self.ocp4._display_tag_for(['ironic'], 'image', is_excluded=True)
        self.assertEqual(tag, ' [images except ironic]')

        # More than one image excluded
        tag = self.ocp4._display_tag_for(['image1', 'image2'], 'image', is_excluded=True)
        self.assertEqual(tag, ' [images except 2]')

        # One RPM excluded
        tag = self.ocp4._display_tag_for(['python-ansible'], 'rpm', is_excluded=True)
        self.assertEqual(tag, ' [rpms except python-ansible]')

        # More than one image excluded
        tag = self.ocp4._display_tag_for(['rpm1', 'rpm2'], 'rpm', is_excluded=True)
        self.assertEqual(tag, ' [rpms except 2]')

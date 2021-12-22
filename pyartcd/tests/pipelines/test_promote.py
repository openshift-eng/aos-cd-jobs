import asyncio
from pathlib import Path
from unittest import TestCase

from mock import AsyncMock, MagicMock, patch
from mock.mock import ANY
from pyartcd.pipelines.promote import PromotePipeline


class TestPromotePipeline(TestCase):
    @patch("pyartcd.pipelines.promote.util.load_releases_config", return_value={})
    @patch("pyartcd.pipelines.promote.util.load_group_config", return_value={})
    def test_run_without_explicit_assembly_definition(self, load_group_config: AsyncMock, load_releases_config: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, "openshift-4.10", "4.10.99", None, ["x86_64", "s390x"], False, False)
        with self.assertRaisesRegex(ValueError, "must be explictly defined"):
            asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "4.10.99", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))

    @patch("pyartcd.pipelines.promote.util.load_releases_config", return_value={
        "releases": {"stream": {"assembly": {"type": "stream"}}}
    })
    @patch("pyartcd.pipelines.promote.util.load_group_config", return_value={})
    def test_run_with_stream_assembly(self, load_group_config: AsyncMock, load_releases_config: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, "openshift-4.10", "stream", None, ["x86_64", "s390x"], False, False)
        with self.assertRaisesRegex(ValueError, "not supported"):
            asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "stream", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))

    @patch("pyartcd.pipelines.promote.util.load_releases_config", return_value={
        "releases": {"art0001": {"assembly": {"type": "custom"}}}
    })
    @patch("pyartcd.pipelines.promote.util.load_group_config", return_value={})
    def test_run_with_custom_assembly_and_missing_release_offset(self, load_group_config: AsyncMock, load_releases_config: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, "openshift-4.10", "art0001", None, ["x86_64", "s390x"], False, False)
        with self.assertRaisesRegex(ValueError, "release_offset is required"):
            asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "art0001", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))

    @patch("pyartcd.pipelines.promote.PromotePipeline.build_release_image", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_release_image_info", side_effect=lambda pullspec, raise_if_not_found=False: {
        "image": pullspec,
        "digest": f"fake:deadbeef-{pullspec}",
        "references": {
            "spec": {
                "tags": [
                    {
                        "name": "machine-os-content",
                        "annotations": {"io.openshift.build.versions": "machine-os=00.00.212301010000-0"}
                    }
                ]
            }
        }
    } if raise_if_not_found else None)
    @patch("pyartcd.pipelines.promote.util.load_releases_config", return_value={
        "releases": {"art0001": {"assembly": {"type": "custom"}}}
    })
    @patch("pyartcd.pipelines.promote.util.load_group_config", return_value={})
    def test_run_with_custom_assembly(self, load_group_config: AsyncMock, load_releases_config: AsyncMock, get_release_image_info: AsyncMock,
                                      build_release_image: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, "openshift-4.10", "art0001", "99", ["x86_64", "s390x"], False, False)
        pipeline._slack_client = AsyncMock()
        asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "art0001", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-x86_64", raise_if_not_found=ANY)
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-s390x", raise_if_not_found=ANY)
        build_release_image.assert_any_await("4.10.99-assembly.art0001", "x86_64", [], {}, "quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-x86_64", None)
        build_release_image.assert_any_await("4.10.99-assembly.art0001", "s390x", [], {}, "quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-s390x", None)
        pipeline._slack_client.bind_channel.assert_called_once_with("4.10.99-assembly.art0001")

    @patch("pyartcd.pipelines.promote.util.load_releases_config", return_value={
        "releases": {"4.10.99": {"assembly": {"type": "standard"}}}
    })
    @patch("pyartcd.pipelines.promote.util.load_group_config", return_value={})
    def test_run_with_standard_assembly_without_upgrade_edges(self, load_group_config: AsyncMock, load_releases_config: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, "openshift-4.10", "4.10.99", None, ["x86_64", "s390x"], False, False)
        pipeline._slack_client = AsyncMock()
        with self.assertRaisesRegex(ValueError, "missing the required `upgrades` field"):
            asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "4.10.99", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))

    @patch("pyartcd.pipelines.promote.PromotePipeline.build_release_image", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_release_image_info", side_effect=lambda pullspec, raise_if_not_found=False: {
        "image": pullspec,
        "digest": f"fake:deadbeef-{pullspec}",
        "references": {
            "spec": {
                "tags": [
                    {
                        "name": "machine-os-content",
                        "annotations": {"io.openshift.build.versions": "machine-os=00.00.212301010000-0"}
                    }
                ]
            }
        }
    } if raise_if_not_found else None)
    @patch("pyartcd.pipelines.promote.util.load_releases_config", return_value={
        "releases": {"4.10.99": {"assembly": {"type": "standard"}}}
    })
    @patch("pyartcd.pipelines.promote.util.load_group_config", return_value={
        "upgrades": "4.10.98,4.9.99",
        "advisories": {"rpm": 1, "image": 2, "extras": 3, "metadata": 4},
        "description": "whatever",
    })
    def test_run_with_standard_assembly(self, load_group_config: AsyncMock, load_releases_config: AsyncMock,
                                        get_release_image_info: AsyncMock, build_release_image: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}},
                            working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, "openshift-4.10", "4.10.99", None, ["x86_64", "s390x", "ppc64le", "aarch64"], False, False)
        pipeline._slack_client = AsyncMock()
        pipeline.check_blocker_bugs = AsyncMock()
        pipeline.attach_cve_flaws = AsyncMock()
        pipeline.get_advisory_info = AsyncMock(return_value={
            "id": 2,
            "errata_id": 2222,
            "fulladvisory": "RHBA-2099:2222-02",
            "status": "QE",
        })
        pipeline.verify_attached_bugs = AsyncMock(return_value=None)
        pipeline.get_image_stream_tag = AsyncMock(return_value=None)
        pipeline.tag_release = AsyncMock(return_value=None)
        pipeline.wait_for_stable = AsyncMock(return_value=None)
        pipeline.send_image_list_email = AsyncMock()
        asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "4.10.99", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))
        pipeline.check_blocker_bugs.assert_awaited_once_with()
        for advisory in [1, 2, 3, 4]:
            pipeline.attach_cve_flaws.assert_any_await(advisory)
        pipeline.get_advisory_info.assert_awaited_once_with(2)
        pipeline.verify_attached_bugs.assert_awaited_once_with([1, 2, 3, 4])
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64", raise_if_not_found=ANY)
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-s390x", raise_if_not_found=ANY)
        build_release_image.assert_any_await("4.10.99", "x86_64", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64", None)
        build_release_image.assert_any_await("4.10.99", "s390x", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-s390x", None)
        build_release_image.assert_any_await("4.10.99", "ppc64le", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-ppc64le", None)
        build_release_image.assert_any_await("4.10.99", "aarch64", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64", None)
        pipeline._slack_client.bind_channel.assert_called_once_with("4.10.99")
        pipeline.get_image_stream_tag.assert_any_await("ocp", "release:4.10.99")
        pipeline.tag_release.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64", "ocp/release:4.10.99")
        pipeline.tag_release.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-s390x", "ocp-s390x/release-s390x:4.10.99")
        pipeline.tag_release.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-ppc64le", "ocp-ppc64le/release-ppc64le:4.10.99")
        pipeline.tag_release.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64", "ocp-arm64/release-arm64:4.10.99")
        pipeline.wait_for_stable.assert_any_await("4.10.99", "x86_64", "4-stable")
        pipeline.wait_for_stable.assert_any_await("4.10.99", "s390x", "4-stable-s390x")
        pipeline.wait_for_stable.assert_any_await("4.10.99", "ppc64le", "4-stable-ppc64le")
        pipeline.wait_for_stable.assert_any_await("4.10.99", "aarch64", "4-stable-arm64")
        pipeline.send_image_list_email.assert_awaited_once_with("4.10.99", 2, ANY)

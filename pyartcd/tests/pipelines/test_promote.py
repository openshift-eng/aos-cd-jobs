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
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x"])
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
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="stream", release_offset=None, arches=["x86_64", "s390x"])
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
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="art0001", release_offset=None, arches=["x86_64", "s390x"])
        with self.assertRaisesRegex(ValueError, "release_offset is required"):
            asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "art0001", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))

    @patch("pyartcd.pipelines.promote.PromotePipeline.build_release_image", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_release_image_info", side_effect=lambda pullspec, raise_if_not_found=False: {
        "image": pullspec,
        "digest": f"fake:deadbeef-{pullspec}",
        "metadata": {
            "version": "4.10.99-assembly.art0001",
        },
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
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="art0001", release_offset=99, arches=["x86_64", "s390x"])
        pipeline._slack_client = AsyncMock()
        asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "art0001", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-x86_64", raise_if_not_found=ANY)
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-s390x", raise_if_not_found=ANY)
        build_release_image.assert_any_await("4.10.99-assembly.art0001", "x86_64", [], {}, "quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-x86_64", None, '4.10-art-assembly-art0001', keep_manifest_list=False)
        build_release_image.assert_any_await("4.10.99-assembly.art0001", "s390x", [], {}, "quay.io/openshift-release-dev/ocp-release:4.10.99-assembly.art0001-s390x", None, '4.10-art-assembly-art0001-s390x', keep_manifest_list=False)
        pipeline._slack_client.bind_channel.assert_called_once_with("4.10.99-assembly.art0001")

    @patch("pyartcd.pipelines.promote.util.load_releases_config", return_value={
        "releases": {"4.10.99": {"assembly": {"type": "standard"}}}
    })
    @patch("pyartcd.pipelines.promote.util.load_group_config", return_value={})
    def test_run_with_standard_assembly_without_upgrade_edges(self, load_group_config: AsyncMock, load_releases_config: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}}, working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x"])
        pipeline._slack_client = AsyncMock()
        with self.assertRaisesRegex(ValueError, "missing the required `upgrades` field"):
            asyncio.get_event_loop().run_until_complete(pipeline.run())
        load_group_config.assert_awaited_once_with("openshift-4.10", "4.10.99", env=ANY)
        load_releases_config.assert_awaited_once_with(Path("/path/to/working/doozer-working/ocp-build-data"))

    @patch("pyartcd.pipelines.promote.PromotePipeline.build_release_image", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_release_image_info", side_effect=lambda pullspec, raise_if_not_found=False: {
        "image": pullspec,
        "digest": f"fake:deadbeef-{pullspec}",
        "metadata": {
            "version": "4.10.99",
        },
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
        "releases": {"4.10.99": {"assembly": {"type": "standard", "basis": {"reference_releases": {
            "x86_64": "nightly-x86_64",
            "s390x": "nightly-s390x",
            "ppc64le": "nightly-ppc64le",
            "aarch64": "nightly-aarch64",
        }}}}}
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
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x", "ppc64le", "aarch64"])
        pipeline._slack_client = AsyncMock()
        pipeline.check_blocker_bugs = AsyncMock()
        pipeline.attach_cve_flaws = AsyncMock()
        pipeline.change_advisory_state = AsyncMock()
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
            pipeline.change_advisory_state.assert_any_await(advisory, "QE")
        pipeline.get_advisory_info.assert_awaited_once_with(2)
        pipeline.verify_attached_bugs.assert_awaited_once_with([1, 2, 3, 4])
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64", raise_if_not_found=ANY)
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-s390x", raise_if_not_found=ANY)
        build_release_image.assert_any_await("4.10.99", "x86_64", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64", "registry.ci.openshift.org/ocp/release:nightly-x86_64", None, keep_manifest_list=False)
        build_release_image.assert_any_await("4.10.99", "s390x", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-s390x", "registry.ci.openshift.org/ocp-s390x/release-s390x:nightly-s390x", None, keep_manifest_list=False)
        build_release_image.assert_any_await("4.10.99", "ppc64le", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-ppc64le", "registry.ci.openshift.org/ocp-ppc64le/release-ppc64le:nightly-ppc64le", None, keep_manifest_list=False)
        build_release_image.assert_any_await("4.10.99", "aarch64", ["4.10.98", "4.9.99"], {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}, "quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64", "registry.ci.openshift.org/ocp-arm64/release-arm64:nightly-aarch64", None, keep_manifest_list=False)
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

    @patch("pyartcd.pipelines.promote.PromotePipeline.tag_release", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_image_stream_tag", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.build_release_image", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_release_image_info", side_effect=lambda pullspec, raise_if_not_found=False: {
        "image": pullspec,
        "digest": "fake:deadbeef",
        "metadata": {
            "version": "4.10.99",
        },
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
    def test_promote_arch(self, get_release_image_info: AsyncMock, build_release_image: AsyncMock, get_image_stream_tag: AsyncMock, tag_release: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}},
                            working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x", "ppc64le", "aarch64"])
        previous_list = ["4.10.98", "4.10.97", "4.9.99"]
        metadata = {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}

        # test x86_64
        reference_release = "whatever-x86_64"
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_arch(release_name="4.10.99", arch="x86_64", previous_list=previous_list, metadata=metadata, reference_release=reference_release, tag_stable=True))
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64")
        build_release_image.assert_awaited_once_with("4.10.99", "x86_64", previous_list, metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64", f'registry.ci.openshift.org/ocp/release:{reference_release}', None, keep_manifest_list=False)
        get_image_stream_tag.assert_awaited_once_with("ocp", "release:4.10.99")
        tag_release.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64", "ocp/release:4.10.99")
        self.assertEqual(actual["image"], "quay.io/openshift-release-dev/ocp-release:4.10.99-x86_64")

        # test aarch64
        reference_release = "whatever-aarch64"
        get_release_image_info.reset_mock()
        build_release_image.reset_mock()
        get_image_stream_tag.reset_mock()
        tag_release.reset_mock()
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_arch(release_name="4.10.99", arch="aarch64", previous_list=previous_list, metadata=metadata, reference_release=reference_release, tag_stable=True))
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64")
        build_release_image.assert_awaited_once_with("4.10.99", "aarch64", previous_list, metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64", f'registry.ci.openshift.org/ocp-arm64/release-arm64:{reference_release}', None, keep_manifest_list=False)
        get_image_stream_tag.assert_awaited_once_with("ocp-arm64", "release-arm64:4.10.99")
        tag_release.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64", "ocp-arm64/release-arm64:4.10.99")
        self.assertEqual(actual["image"], "quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64")

        # test release tag already exists but doesn't match the to-be-promoted release image
        get_image_stream_tag.return_value = {
            "image": {
                "dockerImageReference": "quay.io/openshift-release-dev/ocp-release@fake:foobar",
            }
        }
        reference_release = "whatever-aarch64"
        get_release_image_info.reset_mock()
        build_release_image.reset_mock()
        get_image_stream_tag.reset_mock()
        tag_release.reset_mock()
        with self.assertRaisesRegex(ValueError, "already exists, but it has a different digest"):
            asyncio.get_event_loop().run_until_complete(pipeline._promote_arch(release_name="4.10.99", arch="aarch64", previous_list=previous_list, metadata=metadata, reference_release=reference_release, tag_stable=True))
        get_release_image_info.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64")
        build_release_image.assert_awaited_once_with("4.10.99", "aarch64", previous_list, metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-aarch64", f'registry.ci.openshift.org/ocp-arm64/release-arm64:{reference_release}', None, keep_manifest_list=False)
        get_image_stream_tag.assert_awaited_once_with("ocp-arm64", "release-arm64:4.10.99")
        tag_release.assert_not_awaited()

    @patch("pyartcd.pipelines.promote.exectools.cmd_assert_async", return_value=0)
    def test_build_release_image_from_reference_release(self, cmd_assert_async: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}},
                            working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x", "ppc64le", "aarch64"])
        previous_list = ["4.10.98", "4.10.97", "4.9.99"]
        metadata = {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}

        # test x86_64
        reference_release = "registry.ci.openshift.org/ocp/release:whatever-x86_64"
        dest_pullspec = "example.com/foo/release:4.10.99-x86_64"
        asyncio.get_event_loop().run_until_complete(pipeline.build_release_image("4.10.99", "x86_64", previous_list, metadata, dest_pullspec, reference_release, None, keep_manifest_list=False))
        expected_cmd = ["oc", "adm", "release", "new", "-n", "ocp", "--name=4.10.99", "--to-image=example.com/foo/release:4.10.99-x86_64", f"--from-release={reference_release}", "--previous=4.10.98,4.10.97,4.9.99", "--metadata", "{\"description\": \"whatever\", \"url\": \"https://access.redhat.com/errata/RHBA-2099:2222\"}"]
        cmd_assert_async.assert_awaited_once_with(expected_cmd, env=ANY, stdout=ANY)

        # test aarch64
        reference_release = "registry.ci.openshift.org/ocp-arm64/release-arm64:whatever-aarch64"
        dest_pullspec = "example.com/foo/release:4.10.99-aarch64"
        cmd_assert_async.reset_mock()
        asyncio.get_event_loop().run_until_complete(pipeline.build_release_image("4.10.99", "aarch64", previous_list, metadata, dest_pullspec, reference_release, None, keep_manifest_list=False))
        expected_cmd = ["oc", "adm", "release", "new", "-n", "ocp-arm64", "--name=4.10.99", "--to-image=example.com/foo/release:4.10.99-aarch64", f"--from-release={reference_release}", "--previous=4.10.98,4.10.97,4.9.99", "--metadata", "{\"description\": \"whatever\", \"url\": \"https://access.redhat.com/errata/RHBA-2099:2222\"}"]
        cmd_assert_async.assert_awaited_once_with(expected_cmd, env=ANY, stdout=ANY)

        # test multi-aarch64
        reference_release = "registry.ci.openshift.org/ocp-arm64/release-arm64:whatever-multi-aarch64"
        dest_pullspec = "example.com/foo/release:4.10.99-multi-aarch64"
        cmd_assert_async.reset_mock()
        asyncio.get_event_loop().run_until_complete(pipeline.build_release_image("4.10.99", "aarch64", previous_list, metadata, dest_pullspec, reference_release, None, keep_manifest_list=True))
        expected_cmd = ["oc", "adm", "release", "new", "-n", "ocp-arm64", "--name=4.10.99", "--to-image=example.com/foo/release:4.10.99-multi-aarch64", f"--from-release={reference_release}", "--keep-manifest-list", "--previous=4.10.98,4.10.97,4.9.99", "--metadata", "{\"description\": \"whatever\", \"url\": \"https://access.redhat.com/errata/RHBA-2099:2222\"}"]
        cmd_assert_async.assert_awaited_once_with(expected_cmd, env=ANY, stdout=ANY)

    @patch("pyartcd.pipelines.promote.exectools.cmd_assert_async", return_value=0)
    def test_build_release_image_from_image_stream(self, cmd_assert_async: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}},
                            working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x", "ppc64le", "aarch64"])
        previous_list = ["4.10.98", "4.10.97", "4.9.99"]
        metadata = {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}

        # test x86_64
        reference_release = None
        dest_pullspec = "example.com/foo/release:4.10.99-x86_64"
        from_image_stream = "4.10-art-assembly-4.10.99"
        asyncio.get_event_loop().run_until_complete(pipeline.build_release_image("4.10.99", "x86_64", previous_list, metadata, dest_pullspec, reference_release, from_image_stream, keep_manifest_list=False))
        expected_cmd = ['oc', 'adm', 'release', 'new', '-n', 'ocp', '--name=4.10.99', '--to-image=example.com/foo/release:4.10.99-x86_64', '--reference-mode=source', '--from-image-stream=4.10-art-assembly-4.10.99', '--previous=4.10.98,4.10.97,4.9.99', '--metadata', '{"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}']
        cmd_assert_async.assert_awaited_once_with(expected_cmd, env=ANY, stdout=ANY)

        # test aarch64
        reference_release = None
        dest_pullspec = "example.com/foo/release:4.10.99-aarch64"
        from_image_stream = "4.10-art-assembly-4.10.99-arm64"
        cmd_assert_async.reset_mock()
        asyncio.get_event_loop().run_until_complete(pipeline.build_release_image("4.10.99", "aarch64", previous_list, metadata, dest_pullspec, reference_release, from_image_stream, keep_manifest_list=False))
        expected_cmd = ['oc', 'adm', 'release', 'new', '-n', 'ocp-arm64', '--name=4.10.99', '--to-image=example.com/foo/release:4.10.99-aarch64', '--reference-mode=source', '--from-image-stream=4.10-art-assembly-4.10.99-arm64', '--previous=4.10.98,4.10.97,4.9.99', '--metadata', '{"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}']
        cmd_assert_async.assert_awaited_once_with(expected_cmd, env=ANY, stdout=ANY)

    @patch("pyartcd.pipelines.promote.PromotePipeline.tag_release", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_image_stream_tag", return_value={
        "tag": {
            "from": {
                "name": "quay.io/openshift-release-dev/ocp-release:4.10.99-multi",
            }
        }
    })
    @patch("pyartcd.pipelines.promote.PromotePipeline.push_manifest_list", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.build_release_image", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_image_stream", return_value={
        "spec": {
            "tags": [
                {"name": "4.10.99-0.art-assembly-4.10.99-multi-2022-07-26-210300",
                 "from": {"name": "example.com/ocp-release@fake:deadbeef-source-manifest-list"}}
            ]
        }
    })
    @patch('pyartcd.pipelines.promote.PromotePipeline.get_image_info', side_effect=lambda pullspec, raise_if_not_found=False: {
        ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-amd64",
                    "platform": {
                        "architecture": "amd64",
                        "os": "linux"
                    }
                },
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-ppc64le",
                    "platform": {
                        "architecture": "ppc64le",
                        "os": "linux"
                    }
                },
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-s390x",
                    "platform": {
                        "architecture": "s390x",
                        "os": "linux"
                    }
                },
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-aarch64",
                    "platform": {
                        "architecture": "arm64",
                        "os": "linux"
                    }
                }
            ]
        },
    }[pullspec, raise_if_not_found])
    @patch('pyartcd.pipelines.promote.PromotePipeline.get_image_digest', return_value='fake:deadbeef-toplevel-manifest-list')
    def test_promote_heterogeneous_payload(self, get_image_digest: AsyncMock, get_image_info: AsyncMock, get_image_stream: AsyncMock,
                                           build_release_image: AsyncMock, push_manifest_list: AsyncMock, get_image_stream_tag: AsyncMock, tag_release: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}},
                            working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x", "ppc64le", "aarch64"])
        previous_list = ["4.10.98", "4.10.97", "4.9.99"]
        metadata = {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}

        # test: heterogeneous payload already exists
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_heterogeneous_payload(release_name="4.10.99", include_arches=["x86_64", "aarch64"], previous_list=previous_list, metadata=metadata, tag_stable=True))
        get_image_digest.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        get_image_info.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", raise_if_not_found=True)
        get_image_stream_tag.assert_awaited_once_with("ocp-multi", "release-multi:4.10.99")
        build_release_image.assert_not_called()
        tag_release.assert_not_called()

        # test: promote a GA heterogeneous payload
        get_image_digest.reset_mock()
        get_image_digest.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", False): None,
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): "fake:deadbeef-dest-multi",
        }[pullspec, raise_if_not_found]
        get_image_info.reset_mock()
        get_image_info.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): None,
            ('example.com/ocp-release@fake:deadbeef-source-manifest-list', True): {
                "schemaVersion": 2,
                "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
                "manifests": [
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-amd64",
                        "platform": {
                            "architecture": "amd64",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-ppc64le",
                        "platform": {
                            "architecture": "ppc64le",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-s390x",
                        "platform": {
                            "architecture": "s390x",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-arm64",
                        "platform": {
                            "architecture": "arm64",
                            "os": "linux"
                        }
                    }
                ]
            }
        }[pullspec, raise_if_not_found]
        get_image_stream.reset_mock()
        get_image_stream_tag.reset_mock()
        get_image_stream_tag.return_value = None
        build_release_image.reset_mock()
        push_manifest_list.reset_mock()
        tag_release.reset_mock()
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_heterogeneous_payload(release_name="4.10.99", include_arches=["x86_64", "aarch64"], previous_list=previous_list, metadata=metadata, tag_stable=True))
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", raise_if_not_found=True)
        get_image_info.assert_awaited_once_with("example.com/ocp-release@fake:deadbeef-source-manifest-list", raise_if_not_found=True)
        get_image_stream.assert_awaited_once_with("ocp-multi", "4.10-art-assembly-4.10.99-multi")
        get_image_stream_tag.assert_awaited_once_with("ocp-multi", "release-multi:4.10.99")
        dest_metadata = metadata.copy()
        dest_metadata["release.openshift.io/architecture"] = "multi"
        build_release_image.assert_any_await("4.10.99", "aarch64", previous_list, dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64", 'example.com/ocp-release@fake:deadbeef-source-multi-arm64', None, keep_manifest_list=True)
        build_release_image.assert_any_await("4.10.99", "x86_64", previous_list, dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64", 'example.com/ocp-release@fake:deadbeef-source-multi-amd64', None, keep_manifest_list=True)
        dest_manifest_list = {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi', 'manifests': [{'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64', 'platform': {'os': 'linux', 'architecture': 'amd64'}}, {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64', 'platform': {'os': 'linux', 'architecture': 'arm64'}}]}
        push_manifest_list.assert_awaited_once_with("4.10.99", dest_manifest_list)
        tag_release.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", "ocp-multi/release-multi:4.10.99")
        self.assertEqual(actual["image"], "quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        self.assertEqual(actual["digest"], "fake:deadbeef-dest-multi")

        # test: promote GA heterogeneous payload
        get_image_digest.reset_mock()
        get_image_digest.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", False): None,
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): "fake:deadbeef-dest-multi",
        }[pullspec, raise_if_not_found]
        get_image_info.reset_mock()
        get_image_info.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): None,
            ('example.com/ocp-release@fake:deadbeef-source-manifest-list', True): {
                "schemaVersion": 2,
                "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
                "manifests": [
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-amd64",
                        "platform": {
                            "architecture": "amd64",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-ppc64le",
                        "platform": {
                            "architecture": "ppc64le",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-s390x",
                        "platform": {
                            "architecture": "s390x",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-arm64",
                        "platform": {
                            "architecture": "arm64",
                            "os": "linux"
                        }
                    }
                ]
            }
        }[pullspec, raise_if_not_found]
        get_image_stream.reset_mock()
        get_image_stream_tag.reset_mock()
        get_image_stream_tag.return_value = None
        build_release_image.reset_mock()
        push_manifest_list.reset_mock()
        tag_release.reset_mock()
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_heterogeneous_payload(release_name="4.10.99", include_arches=["x86_64", "aarch64"], previous_list=previous_list, metadata=metadata, tag_stable=True))
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", raise_if_not_found=True)
        get_image_info.assert_awaited_once_with("example.com/ocp-release@fake:deadbeef-source-manifest-list", raise_if_not_found=True)
        get_image_stream.assert_awaited_once_with("ocp-multi", "4.10-art-assembly-4.10.99-multi")
        get_image_stream_tag.assert_awaited_once_with("ocp-multi", "release-multi:4.10.99")
        dest_metadata = metadata.copy()
        dest_metadata["release.openshift.io/architecture"] = "multi"
        build_release_image.assert_any_await("4.10.99", "aarch64", previous_list, dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64", 'example.com/ocp-release@fake:deadbeef-source-multi-arm64', None, keep_manifest_list=True)
        build_release_image.assert_any_await("4.10.99", "x86_64", previous_list, dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64", 'example.com/ocp-release@fake:deadbeef-source-multi-amd64', None, keep_manifest_list=True)
        dest_manifest_list = {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi', 'manifests': [{'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64', 'platform': {'os': 'linux', 'architecture': 'amd64'}}, {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64', 'platform': {'os': 'linux', 'architecture': 'arm64'}}]}
        push_manifest_list.assert_awaited_once_with("4.10.99", dest_manifest_list)
        tag_release.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", "ocp-multi/release-multi:4.10.99")
        self.assertEqual(actual["image"], "quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        self.assertEqual(actual["digest"], "fake:deadbeef-dest-multi")

    @patch("pyartcd.pipelines.promote.PromotePipeline.tag_release", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_image_stream_tag", return_value={
        "tag": {
            "from": {
                "name": "quay.io/openshift-release-dev/ocp-release:4.10.99-multi",
            }
        }
    })
    @patch("pyartcd.pipelines.promote.PromotePipeline.push_manifest_list", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.build_release_image", return_value=None)
    @patch("pyartcd.pipelines.promote.PromotePipeline.get_image_stream", return_value={
        "spec": {
            "tags": [
                {"name": "4.10.99-0.art-assembly-4.10.99-multi-2022-07-26-210300",
                 "from": {"name": "example.com/ocp-release@fake:deadbeef-source-manifest-list"}}
            ]
        }
    })
    @patch('pyartcd.pipelines.promote.PromotePipeline.get_image_info', side_effect=lambda pullspec, raise_if_not_found=False: {
        ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-amd64",
                    "platform": {
                        "architecture": "amd64",
                        "os": "linux"
                    }
                },
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-ppc64le",
                    "platform": {
                        "architecture": "ppc64le",
                        "os": "linux"
                    }
                },
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-s390x",
                    "platform": {
                        "architecture": "s390x",
                        "os": "linux"
                    }
                },
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "size": 1583,
                    "digest": "fake:deadbeef-dest-multi-aarch64",
                    "platform": {
                        "architecture": "arm64",
                        "os": "linux"
                    }
                }
            ]
        },
    }[pullspec, raise_if_not_found])
    @patch('pyartcd.pipelines.promote.PromotePipeline.get_image_digest', return_value='fake:deadbeef-toplevel-manifest-list')
    def test_promote_heterogeneous_payload_with_multi_hack(self, get_image_digest: AsyncMock, get_image_info: AsyncMock, get_image_stream: AsyncMock,
                                                           build_release_image: AsyncMock, push_manifest_list: AsyncMock, get_image_stream_tag: AsyncMock, tag_release: AsyncMock):
        runtime = MagicMock(config={"build_config": {"ocp_build_data_url": "https://example.com/ocp-build-data.git"}},
                            working_dir=Path("/path/to/working"), dry_run=False)
        pipeline = PromotePipeline(runtime, group="openshift-4.10", assembly="4.10.99", release_offset=None, arches=["x86_64", "s390x", "ppc64le", "aarch64"], use_multi_hack=True)
        previous_list = ["4.10.98", "4.10.97", "4.9.99"]
        metadata = {"description": "whatever", "url": "https://access.redhat.com/errata/RHBA-2099:2222"}

        # test: heterogeneous payload already exists
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_heterogeneous_payload(release_name="4.10.99", include_arches=["x86_64", "aarch64"], previous_list=previous_list, metadata=metadata, tag_stable=True))
        get_image_digest.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        get_image_info.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", raise_if_not_found=True)
        get_image_stream_tag.assert_awaited_once_with("ocp-multi", "release-multi:4.10.99-multi")
        build_release_image.assert_not_called()
        tag_release.assert_not_called()

        # test: promote a GA heterogeneous payload
        get_image_digest.reset_mock()
        get_image_digest.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", False): None,
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): "fake:deadbeef-dest-multi",
        }[pullspec, raise_if_not_found]
        get_image_info.reset_mock()
        get_image_info.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): None,
            ('example.com/ocp-release@fake:deadbeef-source-manifest-list', True): {
                "schemaVersion": 2,
                "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
                "manifests": [
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-amd64",
                        "platform": {
                            "architecture": "amd64",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-ppc64le",
                        "platform": {
                            "architecture": "ppc64le",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-s390x",
                        "platform": {
                            "architecture": "s390x",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-arm64",
                        "platform": {
                            "architecture": "arm64",
                            "os": "linux"
                        }
                    }
                ]
            }
        }[pullspec, raise_if_not_found]
        get_image_stream.reset_mock()
        get_image_stream_tag.reset_mock()
        get_image_stream_tag.return_value = None
        build_release_image.reset_mock()
        push_manifest_list.reset_mock()
        tag_release.reset_mock()
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_heterogeneous_payload(release_name="4.10.99", include_arches=["x86_64", "aarch64"], previous_list=previous_list, metadata=metadata, tag_stable=True))
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", raise_if_not_found=True)
        get_image_info.assert_awaited_once_with("example.com/ocp-release@fake:deadbeef-source-manifest-list", raise_if_not_found=True)
        get_image_stream.assert_awaited_once_with("ocp-multi", "4.10-art-assembly-4.10.99-multi")
        get_image_stream_tag.assert_awaited_once_with("ocp-multi", "release-multi:4.10.99-multi")
        dest_metadata = metadata.copy()
        dest_metadata["release.openshift.io/architecture"] = "multi"
        build_release_image.assert_any_await("4.10.99-multi", "aarch64", [], dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64", 'example.com/ocp-release@fake:deadbeef-source-multi-arm64', None, keep_manifest_list=True)
        build_release_image.assert_any_await("4.10.99-multi", "x86_64", [], dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64", 'example.com/ocp-release@fake:deadbeef-source-multi-amd64', None, keep_manifest_list=True)
        dest_manifest_list = {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi', 'manifests': [{'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64', 'platform': {'os': 'linux', 'architecture': 'amd64'}}, {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64', 'platform': {'os': 'linux', 'architecture': 'arm64'}}]}
        push_manifest_list.assert_awaited_once_with("4.10.99-multi", dest_manifest_list)
        tag_release.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", "ocp-multi/release-multi:4.10.99-multi")
        self.assertEqual(actual["image"], "quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        self.assertEqual(actual["digest"], "fake:deadbeef-dest-multi")

        # test: promote GA heterogeneous payload
        get_image_digest.reset_mock()
        get_image_digest.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", False): None,
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): "fake:deadbeef-dest-multi",
        }[pullspec, raise_if_not_found]
        get_image_info.reset_mock()
        get_image_info.side_effect = lambda pullspec, raise_if_not_found=False: {
            ("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", True): None,
            ('example.com/ocp-release@fake:deadbeef-source-manifest-list', True): {
                "schemaVersion": 2,
                "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
                "manifests": [
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-amd64",
                        "platform": {
                            "architecture": "amd64",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-ppc64le",
                        "platform": {
                            "architecture": "ppc64le",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-s390x",
                        "platform": {
                            "architecture": "s390x",
                            "os": "linux"
                        }
                    },
                    {
                        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                        "size": 1583,
                        "digest": "fake:deadbeef-source-multi-arm64",
                        "platform": {
                            "architecture": "arm64",
                            "os": "linux"
                        }
                    }
                ]
            }
        }[pullspec, raise_if_not_found]
        get_image_stream.reset_mock()
        get_image_stream_tag.reset_mock()
        get_image_stream_tag.return_value = None
        build_release_image.reset_mock()
        push_manifest_list.reset_mock()
        tag_release.reset_mock()
        actual = asyncio.get_event_loop().run_until_complete(pipeline._promote_heterogeneous_payload(release_name="4.10.99", include_arches=["x86_64", "aarch64"], previous_list=previous_list, metadata=metadata, tag_stable=True))
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        get_image_digest.assert_any_await("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", raise_if_not_found=True)
        get_image_info.assert_awaited_once_with("example.com/ocp-release@fake:deadbeef-source-manifest-list", raise_if_not_found=True)
        get_image_stream.assert_awaited_once_with("ocp-multi", "4.10-art-assembly-4.10.99-multi")
        get_image_stream_tag.assert_awaited_once_with("ocp-multi", "release-multi:4.10.99-multi")
        dest_metadata = metadata.copy()
        dest_metadata["release.openshift.io/architecture"] = "multi"
        build_release_image.assert_any_await("4.10.99-multi", "aarch64", [], dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64", 'example.com/ocp-release@fake:deadbeef-source-multi-arm64', None, keep_manifest_list=True)
        build_release_image.assert_any_await("4.10.99-multi", "x86_64", [], dest_metadata, "quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64", 'example.com/ocp-release@fake:deadbeef-source-multi-amd64', None, keep_manifest_list=True)
        dest_manifest_list = {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi', 'manifests': [{'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-x86_64', 'platform': {'os': 'linux', 'architecture': 'amd64'}}, {'image': 'quay.io/openshift-release-dev/ocp-release:4.10.99-multi-aarch64', 'platform': {'os': 'linux', 'architecture': 'arm64'}}]}
        push_manifest_list.assert_awaited_once_with("4.10.99-multi", dest_manifest_list)
        tag_release.assert_awaited_once_with("quay.io/openshift-release-dev/ocp-release:4.10.99-multi", "ocp-multi/release-multi:4.10.99-multi")
        self.assertEqual(actual["image"], "quay.io/openshift-release-dev/ocp-release:4.10.99-multi")
        self.assertEqual(actual["digest"], "fake:deadbeef-dest-multi")

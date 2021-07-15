import asyncio
import logging
import os
import re
import shutil
from datetime import datetime
from enum import Enum
from io import TextIOWrapper
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import yaml
from pyartcd import constants, exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.record import parse_record_log
from pyartcd.runtime import Runtime
from pyartcd.util import (isolate_el_version_in_branch,
                          isolate_el_version_in_release)


class RebuildType(Enum):
    IMAGE = 0
    RPM = 1
    RHCOS = 2


class RebuildPipeline:
    """ Rebuilds a component for an assembly """

    def __init__(self, runtime: Runtime, group: str, assembly: str,
                 type: RebuildType, dg_key: str, logger: Optional[logging.Logger] = None):
        if assembly == "stream":
            raise ValueError("You may not rebuild a component for 'stream' assembly.")
        if type in [RebuildType.RPM, RebuildType.IMAGE] and not dg_key:
            raise ValueError("'dg_key' is required.")
        elif type == RebuildType.RHCOS and dg_key:
            raise ValueError("'dg_key' is not supported when rebuilding RHCOS.")

        self.runtime = runtime
        self.group = group
        self.assembly = assembly
        self.type = type
        self.dg_key = dg_key
        self.logger = logger or runtime.logger

        # determines OCP version
        match = re.fullmatch(r"openshift-(\d+).(\d)", group)
        if not match:
            raise ValueError(f"Invalid group name: {match}")
        self._ocp_version = (int(match[1]), int(match[2]))

        # sets environment variables for Doozer
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self.runtime.working_dir / "doozer-working")
        ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url")
        if ocp_build_data_url:
            self._doozer_env_vars["DOOZER_DATA_PATH"] = ocp_build_data_url

    async def run(self):
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
        release = f"{timestamp}.p?"

        if self.type == RebuildType.RPM:
            # Rebases and builds the specified rpm
            nvrs = await self._rebase_and_build_rpm(release)
            if self.runtime.dry_run:
                # fake rpm nvrs for dry run
                nvrs = [
                    f"foo-0.0.1-{timestamp}.p0.git.1234567.assembly.{self.assembly}.el8",
                    f"foo-0.0.1-{timestamp}.p0.git.1234567.assembly.{self.assembly}.el7",
                ]
        elif self.type == RebuildType.IMAGE:
            # Determines RHEL version that the image is based on
            group_config = await self._load_group_config()
            branch = await self._get_image_distgit_branch(group_config)
            el_version = isolate_el_version_in_branch(branch)
            assert isinstance(el_version, int)

            (plashet_a_dir, _, plashet_b_dir, plashet_b_url), _ = await asyncio.gather(
                # Builds plashet repos
                self._build_plashets(timestamp, el_version, group_config),
                # Rebases distgit repo
                self._rebase_image(release),
            )

            # Generates rebuild.repo
            with open(plashet_b_dir / "rebuild.repo", "w") as file:
                self._generate_repo_file_for_image(file, plashet_a_dir.name, plashet_b_url)

            # Copies plashet repos out to rcm-guest
            await asyncio.gather(
                self._copy_plashet_out_to_remote(el_version, plashet_a_dir),
                self._copy_plashet_out_to_remote(el_version, plashet_b_dir),
            )

            # Builds image
            nvrs = await self._build_image(plashet_b_url + "/rebuild.repo")
            if self.runtime.dry_run:
                # Fakes image nvrs for dry run
                nvrs = [
                    f"foo-container-0.0.1-{timestamp}.p0.git.1234567.assembly.{self.assembly}",
                ]
        else:  # self.type == RebuildType.RHCOS:
            # Builds plashet repos
            group_config = await self._load_group_config()
            el_version = 8  # FIXME: Currently RHCOS is based on RHEL8, hardcode RHEL version here
            plashet_a_dir, plashet_a_url, plashet_b_dir, plashet_b_url = await self._build_plashets(timestamp, el_version, group_config)

            # Generates rebuild.repo
            with open(plashet_b_dir / "rebuild.repo", "w") as file:
                self._generate_repo_file_for_rhcos(file, plashet_a_url, plashet_b_url)

            # Copies plashet repos out to rcm-guest
            await asyncio.gather(
                self._copy_plashet_out_to_remote(el_version, plashet_a_dir),
                self._copy_plashet_out_to_remote(el_version, plashet_b_dir),
            )

            # Prints further instructions
            click.secho(f"RHCOS build is not triggered by this job. Please manually run the individual rhcos build jobs on the arch-specific rhcos build clusters with the following Plashet repo:\n\t{plashet_b_url}/rebuild.repo", fg="yellow")

        # Prints example schema
        if self.type in [RebuildType.RPM, RebuildType.IMAGE]:
            click.secho("Build completes. Please update the assembly schema in releases.yaml to pin the following NVR(s) to the assembly:\n", fg="green")
            for nvr in nvrs:
                click.secho(f"\t{nvr}", fg="green")
            example_schema = yaml.safe_dump(self._generate_example_schema(nvrs))
            click.secho(f"\nExample schema:\n\n{example_schema}", fg="green")

    async def _load_group_config(self):
        self.logger.info("Loading group config...")
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "config:read-group",
            "--yaml",
        ]
        _, stdout, _ = await exectools.cmd_gather_async(cmd, env=self._doozer_env_vars)
        group_config = yaml.safe_load(stdout)
        return group_config

    async def _build_plashet_from_tags(self, name: str, el_version: int, arches: List[str], signing_advisory: Optional[int]) -> Tuple[Path, str]:
        self.logger.info("Building plashet A %s for EL%s...", name, el_version)
        """ Builds Plashet repo with "from-tags"
        :param name: Plashet repo name
        :param el_version: RHEL version
        :param arches: List of arch names
        :return: (local_path, remote_url)
        """
        self.logger.info("Building plashet %s - RHEL %s for assembly %s...", name, el_version, self.assembly)
        base_dir = self.runtime.working_dir / f"plashets/el{el_version}/{self.assembly}"
        plashet_dir = base_dir / name
        if plashet_dir.exists():
            shutil.rmtree(plashet_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        signing_mode = "signed"  # We assume rpms used in rebuild job should be always signed
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "config:plashet",
            "--base-dir", str(base_dir),
            "--name", name,
            "--repo-subdir", "os"
        ]
        for arch in arches:
            cmd.extend(["--arch", arch, signing_mode])
        major, minor = self._ocp_version
        cmd.extend([
            "from-tags",
            "--signing-advisory-id", f"{signing_advisory or 54765}",
            "--signing-advisory-mode", "clean",
            "--include-embargoed",
            "--inherit",
            "--embargoed-brew-tag", f"rhaos-{major}.{minor}-rhel-{el_version}-embargoed",
        ])
        # Currently plashet for-assembly only needs rpms from stream assembly plus those pinned by "is" and group dependencies
        if el_version >= 8:
            cmd.extend([
                "--brew-tag", f"rhaos-{major}.{minor}-rhel-{el_version}-candidate", f"OSE-{major}.{minor}-RHEL-{el_version}",
            ])
        else:
            cmd.extend([
                "--brew-tag", f"rhaos-{major}.{minor}-rhel-{el_version}-candidate", f"RHEL-{el_version}-OSE-{major}.{minor}",
            ])
        if self.runtime.dry_run:
            self.logger.warning("[Dry run] Would have run %s", cmd)
        else:
            await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

        remote_url = constants.PLASHET_REMOTE_URL + f"/{major}.{minor}"
        if el_version >= 8:
            remote_url += f"-el{el_version}"
        remote_url += f"/{self.assembly}/{name}"
        return plashet_dir, remote_url

    async def _build_plashet_for_assembly(self, name: str, el_version: int, arches: List[str], signing_advisory: Optional[int]) -> Tuple[Path, str]:
        """ Builds Plashet with "for-assembly"
        :param name: Plashet repo name
        :param el_version: RHEL version
        :param arches: List of arch names
        :return: (local_path, remote_url)
        """
        self.logger.info("Building plashet %s for EL%s...", name, el_version)
        base_dir = self.runtime.working_dir / f"plashets/el{el_version}/{self.assembly}"
        plashet_dir = base_dir / name
        if plashet_dir.exists():
            shutil.rmtree(plashet_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        signing_mode = "signed"  # We assume rpms used in rebuild job should be always signed
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "config:plashet",
            "--base-dir", str(base_dir),
            "--name", name,
            "--repo-subdir", "os"
        ]
        for arch in arches:
            cmd.extend(["--arch", arch, signing_mode])
        cmd.extend([
            "for-assembly",
            "--signing-advisory-id", f"{signing_advisory or 54765}",
            "--signing-advisory-mode", "clean",
            "--el-version", f"{el_version}",
        ])
        if self.type == RebuildType.IMAGE:
            cmd.extend(["--image", self.dg_key])
        elif self.type == RebuildType.RHCOS:
            cmd.append("--rhcos")
        else:
            raise ValueError("Rebuild type is not IMAGE or RHCOS.")
        if self.runtime.dry_run:
            self.logger.warning("[Dry run] Would have run %s", cmd)
        else:
            await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

        major, minor = self._ocp_version
        remote_url = constants.PLASHET_REMOTE_URL + f"/{major}.{minor}"
        if el_version >= 8:
            remote_url += f"-el{el_version}"
        remote_url += f"/{self.assembly}/{name}"
        return plashet_dir, remote_url

    async def _copy_plashet_out_to_remote(self, el_version: int, local_plashet_dir: os.PathLike, symlink_name: Optional[str] = None):
        """ Copies plashet out to remote host (rcm-guest)
        """
        # Make sure the remote base dir exist
        major, minor = self._ocp_version
        remote_dir = f"{constants.PLASHET_REMOTE_BASE_DIR}/{major}.{minor}"
        if el_version >= 8:
            remote_dir += f"-el{el_version}"
        remote_dir += f"/{self.assembly}"
        cmd = [
            "ssh",
            constants.PLASHET_REMOTE_HOST,
            "--",
            "mkdir",
            "-p",
            "--",
            remote_dir,
        ]
        if self.runtime.dry_run:
            self.logger.warning("[DRY RUN] Would have run %s", cmd)
        else:
            await exectools.cmd_assert_async(cmd)

        # Copy local dir to to remote
        cmd = [
            "rsync",
            "-av",
            "--links",
            "--progress",
            "-h",
            "--no-g",
            "--omit-dir-times",
            "--chmod=Dug=rwX,ugo+r",
            "--perms",
            "--",
            f"{local_plashet_dir}",
            f"{constants.PLASHET_REMOTE_HOST}:{remote_dir}"
        ]
        if self.runtime.dry_run:
            self.logger.warning("[DRY RUN] Would have run %s", cmd)
        else:
            await exectools.cmd_assert_async(cmd)

        if symlink_name:
            # Make a symlink
            cmd = [
                "ssh",
                constants.PLASHET_REMOTE_HOST,
                "--",
                "ln",
                "-sfn",
                "--",
                f"{Path(local_plashet_dir).name}",
                f"{remote_dir}/{symlink_name}",
            ]
            if self.runtime.dry_run:
                self.logger.warning("[DRY RUN] Would have run %s", cmd)
            else:
                await exectools.cmd_assert_async(cmd)

    async def _build_plashets(self, timestamp: str, el_version: int, group_config: Dict) -> Tuple[Path, str, Path, str]:
        """ Build plashet repos and return the URL to rebuild.repo
        :return: (plashet_a_dir, plashet_a_url, plashet_b_dir, plashet_b_url)
        """
        if self.type == RebuildType.IMAGE:
            plashet_a_name = f"{self.assembly}-{timestamp}-image-{self.dg_key}-basis"
            plashet_b_name = f"{self.assembly}-{timestamp}-image-{self.dg_key}-overrides"
        elif self.type == RebuildType.RHCOS:
            plashet_a_name = f"{self.assembly}-{timestamp}-rhcos-basis"
            plashet_b_name = f"{self.assembly}-{timestamp}-rhcos-overrides"
        else:
            raise ValueError(f"Building plashets for component type {self.type} is not supported.")

        arches = group_config["arches"]
        signing_advisory = group_config.get("signing_advisory")

        # Builds plashet-A with "from-tags"
        plashet_a_dir, plashet_a_url = await self._build_plashet_from_tags(plashet_a_name, el_version, arches, signing_advisory)

        # Builds plashet-B with "for-assembly"
        plashet_b_dir, plashet_b_url = await self._build_plashet_for_assembly(plashet_b_name, el_version, arches, signing_advisory)

        return plashet_a_dir, plashet_a_url, plashet_b_dir, plashet_b_url

    def _generate_repo_file_for_image(self, file: TextIOWrapper, plashet_a_name: str, plashet_b_url: str):
        # Copy content of .oit/signed.repo in the distgit repo
        source_path = Path(self._doozer_env_vars["DOOZER_WORKING_DIR"]) / f"distgits/containers/{self.dg_key}/.oit/signed.repo"
        content = source_path.read_text()
        content = content.replace("/building-embargoed/", f"/{plashet_a_name}/")  # Let's not use the symlink
        file.write(content)
        file.write("\n")
        # Generate repo entry for plashet-B
        file.writelines([
            "[plashet-rebuild-overrides]\n",
            "name = plashet-rebuild-overrides\n",
            f"baseurl = {plashet_b_url}/$basearch/os\n",
            "enabled = 1\n",
            "priority = 1\n",  # https://wiki.centos.org/PackageManagement/Yum/Priorities
            "gpgcheck = 1\n",
            "gpgkey = file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release\n",
        ])

    def _generate_repo_file_for_rhcos(self, file: TextIOWrapper, plashet_a_url: str, plashet_b_url: str):
        # Generate repo entry for plashet-A
        # See https://gitlab.cee.redhat.com/coreos/redhat-coreos/-/blob/4.7/rhaos.repo
        file.writelines([
            "# These repositories are generated by the OpenShift Automated Release Team\n",
            "# https://issues.redhat.com/browse/ART-3154\n",
            "\n",
            "[plashet-rebuild-basis]\n",
            "name = plashet-rebuild-basis\n",
            f"baseurl = {plashet_a_url}/$basearch/os\n",
            "enabled = 1\n",
            "gpgcheck = 0\n",
            "exclude=nss-altfiles kernel protobuf\n",
        ])
        # Generate repo entry for plashet-B
        file.writelines([
            "[plashet-rebuild-overrides]\n",
            "name = plashet-rebuild-overrides\n",
            f"baseurl = {plashet_b_url}/$basearch/os\n",
            "enabled = 1\n",
            "priority = 1\n",  # https://wiki.centos.org/PackageManagement/Yum/Priorities
            "gpgcheck = 0\n",
            "exclude=nss-altfiles kernel protobuf\n",
        ])

    async def _get_image_distgit_branch(self, group_config: Dict) -> str:
        self.logger.info("Determining distgit branch for image %s...", self.dg_key)
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "-i", self.dg_key,
            "config:print",
            "--yaml",
            "--key", "distgit.branch"
        ]
        _, stdout, _ = await exectools.cmd_gather_async(cmd, env=self._doozer_env_vars)
        image_branch = yaml.safe_load(stdout)["images"][self.dg_key] or group_config["branch"]
        return image_branch

    async def _rebase_image(self, release: str):
        """ Rebases image
        :param release: release field for rebase
        """
        # rebase
        major, minor = self._ocp_version
        version = f"v{major}.{minor}"
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "--latest-parent-version",
            "-i", self.dg_key,
            "images:rebase",
            "--version", version,
            "--release", release,
            "--force-yum-updates",
            "--message", f"Updating Dockerfile version and release {version}-{release}",
        ]
        if not self.runtime.dry_run:
            cmd.append("--push")
        await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

    async def _build_image(self, repo_url: str) -> List[str]:
        """ Builds image
        :param plashet_url: Plashet URL
        :return: NVRs
        """
        # build
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "--latest-parent-version",
            "-i", self.dg_key,
            "images:build",
            "--repo", repo_url,
        ]
        if self.runtime.dry_run:
            cmd.append("--dry-run")

        await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

        if self.runtime.dry_run:
            return []
        # parse record.log
        with open(Path(self._doozer_env_vars["DOOZER_WORKING_DIR"]) / "record.log", "r") as file:
            record_log = parse_record_log(file)
            return record_log["build"][-1]["nvrs"].split(",")

    async def _rebase_and_build_rpm(self, release: str) -> List[str]:
        """ Rebase and build RPM
        :param release: release field for rebase
        :return: NVRs
        """
        major, minor = self._ocp_version
        cmd = [
            "doozer",
            "--group", self.group,
            "--assembly", self.assembly,
            "-r", self.dg_key,
            "rpms:rebase-and-build",
            "--version", f"{major}.{minor}",
            "--release", release,
        ]
        if self.runtime.dry_run:
            cmd.append("--dry-run")
        await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

        if self.runtime.dry_run:
            return []

        # parse record.log
        with open(Path(self._doozer_env_vars["DOOZER_WORKING_DIR"]) / "record.log", "r") as file:
            record_log = parse_record_log(file)
            return record_log["build_rpm"][-1]["nvrs"].split(",")

    def _generate_example_schema(self, nvrs: List[str]) -> Dict:
        is_entry = {}
        if self.type == RebuildType.IMAGE:
            member_type = "images"
            is_entry["nvr"] = nvrs[0]
        elif self.type == RebuildType.RPM:
            member_type = "rpms"
            for nvr in nvrs:
                el_version = isolate_el_version_in_release(nvr)
                assert el_version is not None
                is_entry[f"el{el_version}"] = nvr
        else:
            raise ValueError(f"Generating example schema for {self.type} is not supported")

        schema = {
            "releases": {
                self.assembly: {
                    "assembly": {
                        "members": {
                            member_type: [
                                {
                                    "distgit_key": self.dg_key,
                                    "metadata": {
                                        "is": is_entry
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        return schema


@cli.command("rebuild")
@click.option("-g", "--group", metavar='NAME', required=True,
              help="The group of components on which to operate. e.g. openshift-4.9")
@click.option("--assembly", metavar="ASSEMBLY_NAME", required=True,
              help="The name of an assembly to rebase & build for. e.g. 4.9.1")
@click.option("--type", metavar="BUILD_TYPE", required=True,
              type=click.Choice(("rpm", "image", "rhcos")),
              help="image or rpm or rhcos")
@click.option("--component", "-c", metavar="DISTGIT_KEY",
              help="The name of a component to rebase & build for. e.g. openshift-enterprise-cli")
@pass_runtime
@click_coroutine
async def rebuild(runtime: Runtime, group: str, assembly: str, type: str, component: Optional[str]):
    if type != "rhcos" and not component:
        raise click.BadParameter(f"'--component' is required for type {type}")
    elif type == "rhcos" and component:
        raise click.BadParameter("Option '--component' cannot be used when --type == 'rhcos'")
    pipeline = RebuildPipeline(runtime, group=group, assembly=assembly, type=RebuildType[type.upper()], dg_key=component)
    await pipeline.run()

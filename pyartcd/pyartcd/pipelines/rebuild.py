import asyncio
import logging
import os
import re
import shutil
from collections import namedtuple
from configparser import ConfigParser
from datetime import datetime
from enum import Enum
from io import TextIOWrapper
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import click
import yaml
from doozerlib.assembly import AssemblyTypes
from pyartcd import constants, exectools
from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.record import parse_record_log
from pyartcd.runtime import Runtime
from pyartcd.util import (get_assembly_type, isolate_el_version_in_branch,
                          isolate_el_version_in_release, load_group_config,
                          load_releases_config)


class RebuildType(Enum):
    IMAGE = 0
    RPM = 1
    RHCOS = 2


PlashetBuildResult = namedtuple("PlashetBuildResult", ("repo_name", "local_dir", "remote_url"))


class RebuildPipeline:
    """ Rebuilds a component for an assembly """

    def __init__(self, runtime: Runtime, group: str, assembly: str,
                 type: RebuildType, dg_key: str, ocp_build_data_url: str, logger: Optional[logging.Logger] = None):
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
        self.ocp_build_data_url = ocp_build_data_url

        # determines OCP version
        match = re.fullmatch(r"openshift-(\d+).(\d+)", group)
        if not match:
            raise ValueError(f"Invalid group name: {group}")
        self._ocp_version = (int(match[1]), int(match[2]))

        # sets environment variables for Doozer
        self._doozer_env_vars = os.environ.copy()
        self._doozer_env_vars["DOOZER_WORKING_DIR"] = str(self.runtime.working_dir / "doozer-working")

        if not ocp_build_data_url:
            ocp_build_data_url = self.runtime.config.get("build_config", {}).get("ocp_build_data_url",
                                                                                 constants.OCP_BUILD_DATA_URL)
        if ocp_build_data_url:
            self._doozer_env_vars["DOOZER_DATA_PATH"] = ocp_build_data_url

    async def run(self):
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
        release = f"{timestamp}.p?"

        group_config = await load_group_config(self.group, self.assembly, env=self._doozer_env_vars,
                                               doozer_data_path=self.ocp_build_data_url)
        releases_config = await load_releases_config(
            group=self.group,
            data_path=self.ocp_build_data_url
        )

        if get_assembly_type(releases_config, self.assembly) == AssemblyTypes.STREAM:
            raise ValueError("You may not rebuild a component for a stream assembly.")

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
            image_config = await self._get_meta_config()
            branch = image_config.get("distgit", {}).get("branch", group_config["branch"])
            el_version = isolate_el_version_in_branch(branch)
            if el_version is None:
                raise ValueError(f"Couldn't determine RHEL version for image {self.dg_key}")

            plashets, _ = await asyncio.gather(
                # Builds plashet repos
                self._build_plashets(timestamp, el_version, group_config, image_config),
                # Rebases distgit repo
                self._rebase_image(release),
            )

            # Generates rebuild.repo
            overrides_plashet_dir = plashets[-1][1]
            with open(overrides_plashet_dir / "rebuild.repo", "w") as file:
                self._generate_repo_file_for_image(file, plashets, group_config["arches"])

            # Copies plashet repos out to ocp-artifacts
            await asyncio.gather(*[
                self._copy_plashet_out_to_remote(el_version, plashet[1]) for plashet in plashets
            ])

            # Builds image
            nvrs = await self._build_image(plashets[-1][2] + "/rebuild.repo")
            if self.runtime.dry_run:
                # Fakes image nvrs for dry run
                nvrs = [
                    f"foo-container-0.0.1-{timestamp}.p0.git.1234567.assembly.{self.assembly}",
                ]
        else:  # self.type == RebuildType.RHCOS:
            # Builds plashet repos
            el_version = 8  # FIXME: Currently RHCOS is based on RHEL8, hardcode RHEL version here
            plashets = await self._build_plashets(timestamp, el_version, group_config, None)

            # Generates rebuild.repo
            overrides_plashet_dir = plashets[-1][1]
            with open(overrides_plashet_dir / "rebuild.repo", "w") as file:
                self._generate_repo_file_for_rhcos(file, plashets)

            # Copies plashet repos out to ocp-artifacts
            await asyncio.gather(*[
                self._copy_plashet_out_to_remote(el_version, plashet[1]) for plashet in plashets
            ])

            # Prints further instructions
            click.secho(f"RHCOS build is not triggered by this job. Please manually run the individual rhcos build jobs on the arch-specific rhcos build clusters with the following Plashet repo:\n\t{plashets[-1][2]}/rebuild.repo", fg="yellow")

        # Prints example schema
        if self.type in [RebuildType.RPM, RebuildType.IMAGE]:
            click.secho("Build completes. Please update the assembly schema in releases.yaml to pin the following NVR(s) to the assembly:\n", fg="green")
            for nvr in nvrs:
                click.secho(f"\t{nvr}", fg="green")
            example_schema = yaml.safe_dump(self._generate_example_schema(nvrs))
            click.secho(f"\nExample schema:\n\n{example_schema}", fg="green")

    async def _build_plashet_from_tags(self, name: str, directory_name: str, el_version: int, arches: List[str], tag_pvs: Iterable[Tuple[str, str]], embargoed_tags: Optional[Iterable[str]], signing_advisory: Optional[int]) -> PlashetBuildResult:
        """ Builds Plashet repo with "from-tags"
        :param name: Plashet repo name
        :param directory_name: Directory name for the plashet repo
        :param el_version: RHEL version
        :param arches: List of arch names
        :param tag_pvs: A list of (brew_tag, product_version) whose RPMs should be included in the repo.
        :param tag: a Brew tag name; rpms found in
        :param product_version: Errata product version for this Brew tag
        :param embargoed_tags: If specified, any rpms found in these tags will be considered embargoed (unless they have already shipped)
        :param signing_advisory: If specified, use this advisory for auto-signing
        :return: (repo_name, local_dir, remote_url)
        """
        if not name:
            raise ValueError("`name` cannot be empty.")
        if not directory_name:
            raise ValueError("`directory_name` cannot be empty.")
        if not arches:
            raise ValueError("`arches` cannot be empty.")
        if not tag_pvs:
            raise ValueError("`tag_pvs` cannot be empty.")
        self.logger.info("Building plashet %s - RHEL %s for assembly %s...", directory_name, el_version, self.assembly)
        base_dir = self.runtime.working_dir / f"plashets/el{el_version}/{self.assembly}"
        plashet_dir = base_dir / directory_name
        if plashet_dir.exists():
            shutil.rmtree(plashet_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        signing_mode = "signed"  # We assume rpms used in rebuild job should be always signed
        cmd = [
            "doozer",
            "--data-path", self.ocp_build_data_url,
            "--group", self.group,
            "--assembly", self.assembly,
            "config:plashet",
            "--base-dir", str(base_dir),
            "--name", directory_name,
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
        ])
        if embargoed_tags:
            for t in embargoed_tags:
                cmd.extend(["--embargoed-brew-tag", t])
        # Currently plashet for-assembly only needs rpms from stream assembly plus those pinned by "is" and group dependencies
        for tag, pv in tag_pvs:
            cmd.extend(["--brew-tag", tag, pv])

        if self.runtime.dry_run:
            plashet_dir.mkdir(parents=True, exist_ok=True)
            self.logger.warning("[Dry run] Would have run %s", cmd)
        else:
            await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

        remote_url = constants.PLASHET_REMOTE_URL + f"/{major}.{minor}"
        if el_version >= 8:
            remote_url += f"-el{el_version}"
        remote_url += f"/{self.assembly}/{directory_name}"
        return PlashetBuildResult(name, plashet_dir, remote_url)

    async def _build_plashet_for_assembly(self, name: str, directory_name: str, el_version: int, arches: List[str], signing_advisory: Optional[int]) -> PlashetBuildResult:
        """ Builds Plashet with "for-assembly"
        :param name: Plashet repo name
        :param directory_name: Directory name for the plashet repo
        :param el_version: RHEL version
        :param arches: List of arch names
        :return: (repo_name, local_dir, remote_url)
        """
        if not name:
            raise ValueError("`name` cannot be empty.")
        if not directory_name:
            raise ValueError("`directory_name` cannot be empty.")
        if not arches:
            raise ValueError("`arches` cannot be empty.")
        self.logger.info("Building plashet %s for EL%s...", directory_name, el_version)
        base_dir = self.runtime.working_dir / f"plashets/el{el_version}/{self.assembly}"
        plashet_dir = base_dir / directory_name
        if plashet_dir.exists():
            shutil.rmtree(plashet_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        signing_mode = "signed"  # We assume rpms used in rebuild job should be always signed
        cmd = [
            "doozer",
            "--data-path", self.ocp_build_data_url,
            "--group", self.group,
            "--assembly", self.assembly,
            "config:plashet",
            "--base-dir", str(base_dir),
            "--name", directory_name,
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
            plashet_dir.mkdir(parents=True, exist_ok=True)
            self.logger.warning("[Dry run] Would have run %s", cmd)
        else:
            await exectools.cmd_assert_async(cmd, env=self._doozer_env_vars)

        major, minor = self._ocp_version
        remote_url = constants.PLASHET_REMOTE_URL + f"/{major}.{minor}"
        if el_version >= 8:
            remote_url += f"-el{el_version}"
        remote_url += f"/{self.assembly}/{directory_name}"
        return PlashetBuildResult(name, plashet_dir, remote_url)

    async def _copy_plashet_out_to_remote(self, el_version: int, local_plashet_dir: os.PathLike, symlink_name: Optional[str] = None):
        """ Copies plashet out to remote host (ocp-artifacts)
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

    async def _build_plashets(self, timestamp: str, el_version: int, group_config: Dict, image_config: Optional[Dict]) -> List[PlashetBuildResult]:
        """ Build plashet repos and return the URL to rebuild.repo
        :return: A List of tuples in the form of (repo_name, plashet_dir, plashet_url).
        """
        major, minor = self._ocp_version

        # FIXME: This dict contains config data for creating plashet repos. Maybe someday this should go to ocp-build-data.
        PLASHET_CONFIGS = {
            f"rhel-{el_version}-server-ose-rpms-embargoed": (
                "basis",  # directory name suffix for the basis plashet repo
                f"rhaos-{major}.{minor}-rhel-{el_version}-candidate",  # brew tag
                f"OSE-{major}.{minor}-RHEL-{el_version}" if el_version >= 8 else f"RHEL-{el_version}-OSE-{major}.{minor}",  # product version
            ),
            f"rhel-{el_version}-server-ironic-rpms": (
                "ironic",  # directory name suffix for the basis plashet repo
                f"rhaos-{major}.{minor}-ironic-rhel-{el_version}-candidate",  # brew tag
                f"OSE-IRONIC-{major}.{minor}-RHEL-{el_version}",  # product version
            ),
        }
        EMBARGOED_TAGS = [f"rhaos-{major}.{minor}-rhel-{el_version}-embargoed"]

        arches = group_config["arches"]
        signing_advisory = group_config.get("signing_advisory")

        plashets: List[PlashetBuildResult] = []
        if self.type == RebuildType.IMAGE:
            # Build "basis" plashet repos with "from-tags"
            repos = image_config.get("enabled_repos", []) & PLASHET_CONFIGS.keys()
            for repo in repos:
                plashet_config = PLASHET_CONFIGS[repo]
                basis_repo_dir = f"{self.assembly}-{timestamp}-image-{self.dg_key}-{plashet_config[0]}"
                self.logger.info("Building basis plashet repo %s from Brew tag %s for image %s...", basis_repo_dir, plashet_config[1], self.dg_key)
                plashets.append(await self._build_plashet_from_tags(repo, basis_repo_dir, el_version, arches, (plashet_config[1:3],), EMBARGOED_TAGS, signing_advisory))
            # Build "overrides" plashet repo with "for-assembly"
            overrides_repo_dir = f"{self.assembly}-{timestamp}-image-{self.dg_key}-overrides"
            self.logger.info("Building overrides plashet repo %s from for image %s...", overrides_repo_dir, self.dg_key)
            plashets.append(await self._build_plashet_for_assembly("plashet-rebuild-overrides", overrides_repo_dir, el_version, arches, signing_advisory))
        elif self.type == RebuildType.RHCOS:
            plashet_config = PLASHET_CONFIGS[f"rhel-{el_version}-server-ose-rpms-embargoed"]
            basis_repo_dir = f"{self.assembly}-{timestamp}-rhcos-{plashet_config[0]}"
            overrides_repo_dir = f"{self.assembly}-{timestamp}-rhcos-overrides"
            # Build "basis" plashet repo with "from-tags"
            self.logger.info("Building basis plashet repo %s from Brew tag %s for RHCOS...", basis_repo_dir, plashet_config[1])
            plashets.append(await self._build_plashet_from_tags("plashet-rebuild-basis", basis_repo_dir, el_version, arches, (plashet_config[1:3],), EMBARGOED_TAGS, signing_advisory))
            # Build "overrides" plashet repo with "for-assembly"
            self.logger.info("Building overrides plashet repo %s from for RHCOS...", overrides_repo_dir)
            plashets.append(await self._build_plashet_for_assembly("plashet-rebuild-overrides", overrides_repo_dir, el_version, arches, signing_advisory))
        else:
            raise ValueError(f"Building plashets for component type {self.type} is not supported.")

        return plashets

    def _generate_repo_file_for_image(self, file: TextIOWrapper, plashets: Iterable[PlashetBuildResult], arches):
        # Copy content of .oit/signed.repo in the distgit repo
        source_path = Path(self._doozer_env_vars["DOOZER_WORKING_DIR"]) / f"distgits/containers/{self.dg_key}/.oit/signed.repo"
        repo_content = source_path.read_text()

        yum_repos = ConfigParser()
        yum_repos.read_string(repo_content)

        # Remove original plashet repos
        for repo_name, _, _2 in plashets:
            # remove_section is a no-op on non-existent sections
            yum_repos.remove_section(f"{repo_name}")
            for arch in arches:
                yum_repos.remove_section(f"{repo_name}-{arch}")

        for repo_name, _, repo_url in plashets:
            yum_repos[repo_name] = {}
            yum_repos[repo_name]["name"] = repo_name
            yum_repos[repo_name]["baseurl"] = f"{repo_url}/$basearch/os"
            yum_repos[repo_name]["enabled"] = "1"
            if repo_name == "plashet-rebuild-overrides":
                yum_repos[repo_name]["gpgcheck"] = "0"  # We might have include beta signed / unsigned rpms for overrides
                yum_repos[repo_name]["priority"] = "1"  # https://wiki.centos.org/PackageManagement/Yum/Priorities
            else:
                yum_repos[repo_name]["gpgcheck"] = "1"
                yum_repos[repo_name]["gpgkey"] = "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release"

        file.writelines([
            "# These repositories are generated by the OpenShift Automated Release Team\n",
            "# https://issues.redhat.com/browse/ART-3154\n",
            "\n",
        ])
        yum_repos.write(file)

    def _generate_repo_file_for_rhcos(self, file: TextIOWrapper, plashets: Iterable[PlashetBuildResult]):
        # Generate repo entry for plashet-A
        # See https://gitlab.cee.redhat.com/coreos/redhat-coreos/-/blob/4.7/rhaos.repo
        file.writelines([
            "# These repositories are generated by the OpenShift Automated Release Team\n",
            "# https://issues.redhat.com/browse/ART-3154\n",
            "\n",
        ])
        yum_repos = ConfigParser()
        for repo_name, _, repo_url in plashets:
            yum_repos[repo_name] = {}
            yum_repos[repo_name]["name"] = repo_name
            yum_repos[repo_name]["baseurl"] = f"{repo_url}/$basearch/os"
            yum_repos[repo_name]["enabled"] = "1"
            yum_repos[repo_name]["gpgcheck"] = "0"
            # yum_repos[repo_name]["exclude"] = "nss-altfiles kernel protobuf"
            if repo_name == "plashet-rebuild-overrides":
                yum_repos[repo_name]["priority"] = "1"  # https://wiki.centos.org/PackageManagement/Yum/Priorities
        yum_repos.write(file)

    async def _get_meta_config(self) -> str:
        self.logger.info("Determining distgit branch for image %s...", self.dg_key)
        cmd = [
            "doozer",
            "--data-path", self.ocp_build_data_url,
            "--group", self.group,
            "--assembly", self.assembly,
            "-i", self.dg_key,
            "config:print",
            "--yaml",
        ]
        _, stdout, _ = await exectools.cmd_gather_async(cmd, env=self._doozer_env_vars)
        config = yaml.safe_load(stdout)["images"][self.dg_key]
        return config

    async def _rebase_image(self, release: str):
        """ Rebases image
        :param release: release field for rebase
        """
        # rebase
        major, minor = self._ocp_version
        version = f"v{major}.{minor}"
        cmd = [
            "doozer",
            "--data-path", self.ocp_build_data_url,
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
            "--data-path", self.ocp_build_data_url,
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
            "--data-path", self.ocp_build_data_url,
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
@click.option("--ocp-build-data-url", metavar='BUILD_DATA', default=None,
              help=f"Git repo or directory containing groups metadata e.g. {constants.OCP_BUILD_DATA_URL}")
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
async def rebuild(runtime: Runtime, ocp_build_data_url: str, group: str, assembly: str, type: str, component: Optional[str]):
    if type != "rhcos" and not component:
        raise click.BadParameter(f"'--component' is required for type {type}")
    elif type == "rhcos" and component:
        raise click.BadParameter("Option '--component' cannot be used when --type == 'rhcos'")
    pipeline = RebuildPipeline(runtime, group=group, assembly=assembly, type=RebuildType[type.upper()], dg_key=component, ocp_build_data_url=ocp_build_data_url)
    await pipeline.run()

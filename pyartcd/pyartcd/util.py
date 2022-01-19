import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import aiofiles
import yaml
from doozerlib import assembly, model
from doozerlib.util import brew_arch_for_go_arch, brew_suffix_for_arch, go_arch_for_brew_arch, go_suffix_for_arch

from pyartcd import exectools


def isolate_el_version_in_release(release: str) -> Optional[int]:
    """
    Given a release field, determines whether is contains
    a RHEL version. If it does, it returns the version value as int.
    If it is not found, None is returned.
    """
    match = re.match(r'.*\.el(\d+)(?:\.+|$)', release)
    if match:
        return int(match.group(1))

    return None


def isolate_el_version_in_branch(branch_name: str) -> Optional[int]:
    """
    Given a distgit branch name, determines whether is contains
    a RHEL version. If it does, it returns the version value as int.
    If it is not found, None is returned.
    """
    match = re.fullmatch(r'.*rhel-(\d+).*', branch_name)
    if match:
        return int(match.group(1))

    return None


def isolate_major_minor_in_group(group_name: str) -> Tuple[int, int]:
    """
    Given a group name, determines whether is contains
    a OCP major.minor version. If it does, it returns the version value as (int, int).
    If it is not found, (None, None) is returned.
    """
    match = re.fullmatch(r"openshift-(\d+).(\d+)", group_name)
    if not match:
        return None, None
    return int(match[1]), int(match[2])


async def load_group_config(group: str, assembly: str, env=None) -> Dict:
    cmd = [
        "doozer",
        "--group", group,
        "--assembly", assembly,
        "config:read-group",
        "--yaml",
    ]
    if env is None:
        env = os.environ.copy()
    _, stdout, _ = await exectools.cmd_gather_async(cmd, stderr=None, env=env)
    group_config = yaml.safe_load(stdout)
    if not isinstance(group_config, dict):
        raise ValueError("ocp-build-data contains invalid group config.")
    return group_config


async def load_releases_config(build_data_path: os.PathLike) -> Dict:
    async with aiofiles.open(Path(build_data_path) / "releases.yml", "r") as f:
        content = await f.read()
    return yaml.safe_load(content)


def get_assembly_type(assembly_name: str, releases_config: Dict):
    return assembly.assembly_type(model.Model(releases_config), assembly_name)


def get_release_name(assembly_type: str, group_name: str, assembly_name: str, release_offset: Optional[int]):
    major, minor = isolate_major_minor_in_group(group_name)
    if major is None or minor is None:
        raise ValueError(f"Invalid group name: {group_name}")
    if assembly_type == assembly.AssemblyTypes.CUSTOM:
        if release_offset is None:
            raise ValueError("release_offset is required for a CUSTOM release.")
        release_name = f"{major}.{minor}.{release_offset}-assembly.{assembly_name}"
    elif assembly_type == assembly.AssemblyTypes.CANDIDATE:
        if release_offset is not None:
            raise ValueError("release_offset can't be set for a CANDIDATE release.")
        release_name = f"{major}.{minor}.0-{assembly_name}"
    elif assembly_type == assembly.AssemblyTypes.STANDARD:
        if release_offset is not None:
            raise ValueError("release_offset can't be set for a STANDARD release.")
        release_name = f"{assembly_name}"
    else:
        raise ValueError(f"Assembly type {assembly_type} is not supported.")
    return release_name

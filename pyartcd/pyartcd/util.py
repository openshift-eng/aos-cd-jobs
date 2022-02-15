import os
import re
import functools
import semver
from pathlib import Path
from typing import Dict, Optional, Tuple

import aiofiles
from ruamel.yaml import YAML
from doozerlib import assembly, model
from doozerlib.util import brew_arch_for_go_arch, brew_suffix_for_arch, go_arch_for_brew_arch, go_suffix_for_arch

from pyartcd import exectools

yaml = YAML(typ="safe")


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
    group_config = yaml.load(stdout)
    if not isinstance(group_config, dict):
        raise ValueError("ocp-build-data contains invalid group config.")
    return group_config


async def load_releases_config(build_data_path: os.PathLike) -> Dict:
    async with aiofiles.open(Path(build_data_path) / "releases.yml", "r") as f:
        content = await f.read()
    return yaml.load(content)


def get_assembly_type(releases_config: Dict, assembly_name: str):
    return assembly.assembly_type(model.Model(releases_config), assembly_name)


def get_assmebly_basis(releases_config: Dict, assembly_name: str):
    return assembly.assembly_basis(model.Model(releases_config), assembly_name)


def get_assembly_promotion_permits(releases_config: Dict, assembly_name: str):
    return assembly._assembly_config_struct(model.Model(releases_config), assembly_name, 'promotion_permits', [])


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


def is_assembly_name_candidate(assembly_name):
    return re.match(r'rc\.\d+', assembly_name) or re.match(r'fc\.\d+', assembly_name)


def looks_standard_upgrade_edge(config, assembly_name, major, minor):
    rel_type = config['releases'][assembly_name]['assembly'].get('type', '')
    is_not_custom = rel_type != assembly.AssemblyTypes.CUSTOM.value
    is_candidate = (rel_type == assembly.AssemblyTypes.CANDIDATE.value) or is_assembly_name_candidate(assembly_name)
    looks_standard = re.match(rf'{major}\.{minor}.\d+', assembly_name)
    return is_not_custom and (is_candidate or looks_standard)


def get_valid_semver(assembly_name, major, minor):
    if is_assembly_name_candidate(assembly_name):
        return f'{major}.{minor}.0-{assembly_name}'
    return assembly_name


def sorted_semver(versions):
    return sorted(versions, key=functools.cmp_to_key(semver.compare), reverse=True)


async def get_all_assembly_semvers_for_release(major, minor, build_data_path):
    show_spec = f"origin/openshift-{major}.{minor}:releases.yml"
    cmd = [
        "git",
        "show",
        show_spec,
    ]
    _, stdout, _ = await exectools.cmd_gather_async(cmd, cwd=Path(build_data_path), stderr=None)
    releases_config = yaml.load(stdout)

    assembly_names = [name for name in releases_config['releases'].keys() if looks_standard_upgrade_edge(releases_config, name, major, minor)]
    return [get_valid_semver(name, major, minor) for name in assembly_names]

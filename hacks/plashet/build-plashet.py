#!/usr/bin/env python
# A script to build plashet repos and sync them to ocp-artifacts
# This script is temporarily located in ./hacks.
# It will be migrated to pyartcd once ocp4 job is migrated to Python.

import asyncio
import argparse
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import shlex
import shutil
from typing import Optional, Sequence, Tuple, Union

LOGGER = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--working-dir", required=False, default=".",
                        help="Working directory")
    parser.add_argument("--group", required=True,
                        help="Group name. e.g. openshift-{major}.{minor}")
    parser.add_argument("--assembly", default="stream",
                        help="Assembly name. e.g. stream")
    parser.add_argument("--arch", dest="arches", required=True, action="append",
                        help="[Multiple] Arch name")
    parser.add_argument("--revision", required=True,
                        help="Plashet revision (usually a timestamp). e.g. 202211081230")
    parser.add_argument("--auto-sign", action='store_true',
                        help="Auto sign rpms")
    parser.add_argument("--signing-advisory", type=int,
                        help="Advisory number for auto signing")
    parser.add_argument("--dry-run", action='store_true',
                        help="Don't actually build plashet repos")

    args = parser.parse_args()
    group: str = args.group
    group_pattern = re.compile(r"openshift-(\d+).(\d+)")
    group_match = group_pattern.fullmatch(group)
    if not group_match:
        raise ValueError("Currently only openshift-x.y groups are allowed.")
    major, minor = int(group_match[1]), int(group_match[2])
    revision: str = args.revision
    timestamp = datetime.strptime(revision, "%Y%m%d%H%M%S")
    assembly: str = args.assembly
    arches = args.arches
    signing_mode = "signed" if args.auto_sign else "unsigned"
    signing_advisory: bool = args.signing_advisory
    dry_run = args.dry_run
    PLASHET_CONFIG = {
        "el9-embargoed": {
            "tag": f"rhaos-{major}.{minor}-rhel-9-candidate",
            "product_version": f"OSE-{major}.{minor}-RHEL-9",
            "include_embargoed": True,
            "embargoed_tags": [f"rhaos-{major}.{minor}-rhel-9-embargoed"],
            "include_previous_packages": ["openvswitch", "python3-openvswitch", "ovn", "haproxy", "cri-o"],
        },
        "el9": {
            "tag": f"rhaos-{major}.{minor}-rhel-9-candidate",
            "product_version": f"OSE-{major}.{minor}-RHEL-9",
            "include_embargoed": False,
            "embargoed_tags": [f"rhaos-{major}.{minor}-rhel-9-embargoed"],
            "include_previous_packages": ["openvswitch", "python3-openvswitch", "ovn", "haproxy", "cri-o"],
        },
        "ironic-el9": {
            "tag": f"rhaos-{major}.{minor}-ironic-rhel-9-candidate",
            "product_version": f"OSE-IRONIC-{major}.{minor}-RHEL-9",
            "include_embargoed": False,
            "embargoed_tags": [],  # unlikely to exist until we begin using -gating tag
            "include_previous_packages": [],
        },
        "el8-embargoed": {
            "tag": f"rhaos-{major}.{minor}-rhel-8-candidate",
            "product_version": f"OSE-{major}.{minor}-RHEL-8",
            "include_embargoed": True,
            "embargoed_tags": [f"rhaos-{major}.{minor}-rhel-8-embargoed"],
            "include_previous_packages": ["openvswitch", "python3-openvswitch", "ovn", "haproxy", "cri-o"],
        },
        "el8": {
            "tag": f"rhaos-{major}.{minor}-rhel-8-candidate",
            "product_version": f"OSE-{major}.{minor}-RHEL-8",
            "include_embargoed": False,
            "embargoed_tags": [f"rhaos-{major}.{minor}-rhel-8-embargoed"],
            "include_previous_packages": ["openvswitch", "python3-openvswitch", "ovn", "haproxy", "cri-o"],
        },
    }

    for repo_type, config in PLASHET_CONFIG.items():
        LOGGER.info("Building plashet repo for %s", repo_type)
        base_dir = Path(
            args.working_dir, f"plashets/{major}.{minor}/{assembly}/{repo_type}")
        name = f"{timestamp.year}-{timestamp.month:02}/{revision}"
        include_embargoed = config["include_embargoed"],
        embargoed_tags = config["embargoed_tags"]
        tag_pvs = ((config["tag"], config["product_version"]),)
        print(tag_pvs)
        include_previous_packages = config["include_previous_packages"]
        # We can't safely run doozer config:plashet from-tags in parallel as this moment.
        # Build plashet repos one by one.
        local_path = await build_plashet_from_tags(group=group,
                                                   assembly=assembly,
                                                   base_dir=base_dir,
                                                   name=name,
                                                   arches=arches,
                                                   include_embargoed=include_embargoed,
                                                   signing_mode=signing_mode,
                                                   signing_advisory=signing_advisory,
                                                   embargoed_tags=embargoed_tags,
                                                   tag_pvs=tag_pvs,
                                                   include_previous_packages=include_previous_packages,
                                                   dry_run=dry_run)
        LOGGER.info("Plashet repo for %s created: %s", repo_type, local_path)
        symlink_path = create_latest_symlink(
            base_dir=base_dir, plashet_name=name)
        LOGGER.info("Symlink for %s created: %s", repo_type, symlink_path)

        remote_base_dir = f"/mnt/data/pub/RHOCP/plashets/{major}.{minor}/{assembly}/{repo_type}"
        LOGGER.info("Copying %s to remote host...", base_dir)
        await copy_to_remote(base_dir, remote_base_dir, dry_run=dry_run)


async def build_plashet_from_tags(group: str, assembly: str, base_dir: os.PathLike, name: str, arches: Sequence[str],
                                  include_embargoed: bool, signing_mode: str, signing_advisory: int, tag_pvs: Sequence[Tuple[str, str]],
                                  embargoed_tags: Optional[Sequence[str]], include_previous_packages: Optional[Sequence[str]] = None,
                                  poll_for: int = 0, dry_run: bool = False):
    """ Builds Plashet repo with "from-tags"
    """
    repo_path = Path(base_dir, name)
    if repo_path.exists():
        shutil.rmtree(repo_path)
    cmd = [
        "doozer",
        "--working-dir", "doozer-working",
        "--group", group,
        "--assembly", assembly,
        "config:plashet",
        "--base-dir", str(base_dir),
        "--name", name,
        "--repo-subdir", "os"
    ]
    for arch in arches:
        cmd.extend(["--arch", arch, signing_mode])
    cmd.extend([
        "from-tags",
        "--signing-advisory-id", f"{signing_advisory or 54765}",
        "--signing-advisory-mode", "clean",
        "--inherit",
    ])
    if include_embargoed:
        cmd.append("--include-embargoed")
    if embargoed_tags:
        for t in embargoed_tags:
            cmd.extend(["--embargoed-brew-tag", t])
    for tag, pv in tag_pvs:
        cmd.extend(["--brew-tag", tag, pv])
    for pkg in include_previous_packages:
        cmd.extend(["--include-previous-for", pkg])
    if poll_for:
        cmd.extend(["--poll-for", str(poll_for)])

    if dry_run:
        repo_path.mkdir(parents=True)
        LOGGER.warning("[Dry run] Would have run %s", cmd)
    else:
        LOGGER.info("Executing %s", cmd)
        await cmd_assert_async(cmd, env=os.environ.copy())
    return Path(base_dir, name)


def create_latest_symlink(base_dir: os.PathLike, plashet_name: str):
    symlink_path = Path(base_dir, "latest")
    if symlink_path.is_symlink():
        symlink_path.unlink()
    symlink_path.symlink_to(plashet_name, target_is_directory=True)
    return symlink_path


async def copy_to_remote(local_base_dir: os.PathLike, remote_base_dir: os.PathLike, dry_run: bool = False):
    """ Copies plashet out to remote host (ocp-artifacts)
    """
    # Make sure the remote base dir exist
    PLASHET_REMOTE_HOST = "ocp-artifacts"
    local_base_dir = Path(local_base_dir)
    remote_base_dir = Path(remote_base_dir)
    cmd = [
        "ssh",
        PLASHET_REMOTE_HOST,
        "--",
        "mkdir",
        "-p",
        "--",
        f"{remote_base_dir}",
    ]
    if dry_run:
        LOGGER.warning("[DRY RUN] Would have run %s", cmd)
    else:
        LOGGER.info("Executing %s", cmd)
        await cmd_assert_async(cmd, env=os.environ.copy())

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
        f"{local_base_dir}/",
        f"{PLASHET_REMOTE_HOST}:{remote_base_dir}"
    ]
    if dry_run:
        LOGGER.warning("[DRY RUN] Would have run %s", cmd)
    else:
        LOGGER.info("Executing %s", cmd)
        await cmd_assert_async(cmd, env=os.environ.copy())


async def cmd_assert_async(cmd: Union[Sequence[str], str], check: bool = True, **kwargs) -> int:
    """ Runs a command and optionally raises an exception if the return code of the command indicates failure.
    :param cmd <string|list>: A shell command
    :param check: If check is True and the exit code was non-zero, it raises a ChildProcessError
    :param kwargs: Other arguments passing to asyncio.subprocess.create_subprocess_exec
    :return: return code of the command
    """
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = cmd
    LOGGER.info("Executing:cmd_assert_async %s", cmd_list)
    proc = await asyncio.subprocess.create_subprocess_exec(cmd_list[0], *cmd_list[1:], **kwargs)
    returncode = await proc.wait()
    if returncode != 0:
        msg = f"Process {cmd_list!r} exited with code {returncode}."
        if check:
            raise ChildProcessError(msg)
        else:
            LOGGER.warning(msg)
    return proc.returncode


if __name__ == "__main__":
    asyncio.run(main())

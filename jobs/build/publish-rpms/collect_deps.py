#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote

PACKAGES = [
    "criu",
    "runc",
    "cri-o",
    "cri-tools",
    "skopeo",
    "openshift-clients",
    "openshift-hyperkube",
    "openshift-clients-redistributable",
    "slirp4netns",
    "conmon-rs",
    "openvswitch-selinux-extra-policy",
    "openvswitch2.17"
]

YUM_CONF_TEMPLATES = {
    7: """[main]
cachedir={CACHE_DIR}
keepcache=0
debuglevel=2
exactarch=1
obsoletes=1
gpgcheck=1
plugins=1
installonly_limit=3
reposdir=
skip_missing_names_on_install=0

[rhel-server-7-optional-rpms]
name = rhel-server-7-optional-rpms
baseurl = https://rhsm-pulp.corp.redhat.com/content/dist/rhel/server/7/7Server/{ARCH}/optional/os/
gpgcheck = 0
enabled = 1

[rhel-server-7-extras-rpms]
name = rhel-server-7-extras-rpms
baseurl = https://rhsm-pulp.corp.redhat.com/content/dist/rhel/server/7/7Server/{ARCH}/extras/os/
enabled = 1
gpgcheck = 0

[rhel-server-7-rpms]
name = rhel-server-7-rpms
baseurl = https://rhsm-pulp.corp.redhat.com/content/dist/rhel/server/7/7Server/{ARCH}/os/
enabled = 1
gpgcheck = 0

[rhel-server-7-ose-{OCP_VERSION}-rpms]
name = rhel-server-7-ose-{OCP_VERSION}-rpms
baseurl = https://ocp-artifacts.hosts.prod.psi.rdu2.redhat.com/pub/RHOCP/plashets/{OCP_VERSION}/stream/el7/latest/{ARCH}/os
enabled = 1
gpgcheck = 0
""",
    8: """[main]
cachedir={CACHE_DIR}
keepcache=0
debuglevel=2
exactarch=1
obsoletes=1
gpgcheck=1
plugins=1
installonly_limit=3
reposdir=
skip_missing_names_on_install=0

[rhel-server-8-baseos]
name = rhel-server-8-baseos
baseurl = https://rhsm-pulp.corp.redhat.com/content/dist/rhel8/8/{ARCH}/baseos/os
enabled = 1
gpgcheck = 0

[rhel-server-8-appstream]
name = rhel-server-8-appstream
baseurl = https://rhsm-pulp.corp.redhat.com/content/dist/rhel8/8/{ARCH}/appstream/os/
enabled = 1
gpgcheck = 0

[rhel-server-8-fast-datapath]
name = rhel-server-8-fast-datapath
baseurl = http://rhsm-pulp.corp.redhat.com/content/dist/layered/rhel8/{ARCH}/fast-datapath/os/
enabled = 1
gpgcheck = 0

[rhel-server-8-ose-{OCP_VERSION}-rpms]
name = rhel-server-8-ose-{OCP_VERSION}-rpms
baseurl = https://ocp-artifacts.hosts.prod.psi.rdu2.redhat.com/pub/RHOCP/plashets/{OCP_VERSION}/stream/el8/latest/{ARCH}/os
enabled = 1
gpgcheck = 0
module_hotfixes=1
""",
}

LOGGER = logging.getLogger(__name__)


async def download_rpms(ocp_version: str, arch: str, rhel_major: int, output_dir: os.PathLike):
    yum_conf_tmpl = YUM_CONF_TEMPLATES.get(rhel_major)
    if not yum_conf_tmpl:
        raise ValueError(f"Unsupported RHEL version '{rhel_major}'")

    with tempfile.TemporaryDirectory(prefix="collect_deps-working-", dir=os.curdir) as working_dir:
        working_dir = Path(working_dir).absolute()
        install_root_dir = working_dir / "install-root"
        yum_conf_filename = working_dir / "yum.conf"
        cache_dir = working_dir / "cache"

        yum_conf = yum_conf_tmpl.format(yum_conf_tmpl, OCP_VERSION=quote(
            ocp_version), ARCH=arch, CACHE_DIR=cache_dir).strip()
        with open(yum_conf_filename, "w") as f:
            f.write(yum_conf)
        cmd = [
            "yumdownloader",
            f"--releasever={rhel_major}",
            "-c", f"{yum_conf_filename}",
            "--resolve",
            "--disableplugin=subscription-manager",
            "--downloadonly",
            f"--installroot={Path(install_root_dir).absolute()}",
            f"--destdir={output_dir}",
            f"--arch={arch}",
            "--",
        ] + PACKAGES
        LOGGER.info("Running command %s", cmd)
        env = os.environ.copy()
        # yum doesn't honor cachedir in the yum.conf. It keeps a user specific cache
        # https://unix.stackexchange.com/questions/92257/yum-user-temp-files-var-tmp-yum-fills-up-with-repo-data
        # override the location using TMPDIR
        tmp_dir = working_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        env['TMPDIR'] = str(tmp_dir)
        process = await asyncio.subprocess.create_subprocess_exec(*cmd, env=env)
        rc = await process.wait()
        if rc != 0:
            raise ChildProcessError(f"Process {cmd} exited with status {rc}")


async def create_repo(directory: str):
    cmd = ["createrepo_c", "-v", "--", f"{directory}"]
    LOGGER.info("Running command %s", cmd)
    process = await asyncio.subprocess.create_subprocess_exec(*cmd, env=os.environ.copy())
    rc = await process.wait()
    if rc != 0:
        raise ChildProcessError(f"Process {cmd} exited with status {rc}")


async def collect(ocp_version: str, arch: str, rhel_major: int, base_dir: Optional[str]):
    version_suffix = f"-el{rhel_major}" if rhel_major != 7 else ""
    base_dir = Path(base_dir or ".")
    output_dir = Path(base_dir, f"{ocp_version}{version_suffix}-beta")
    LOGGER.info(
        f"Downloading rpms to {output_dir} for OCP {ocp_version} - RHEL {rhel_major}...")
    await download_rpms(ocp_version, arch, rhel_major, output_dir)
    LOGGER.info(f"Creating repo {output_dir} for {arch} OCP {ocp_version} - RHEL {rhel_major}...")
    await create_repo(output_dir)


async def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", required=False,
                        help="Write repos to specified directory")
    parser.add_argument("--arch", required=False,
                        default='x86_64',
                        help="Write repos to specified directory")
    parser.add_argument("--el", required=False,
                        default='8',
                        help="The RHEL version from which to publish RPMs")
    parser.add_argument("ocp_version", help="OCP version. e.g. 4.11")
    args = parser.parse_args()

    tasks = list()
    tasks.append(collect(args.ocp_version,
                         args.arch,
                         int(args.el), base_dir=args.base_dir))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())

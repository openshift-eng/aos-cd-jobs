import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

import aiofiles
import yaml
import tarfile
import hashlib
import shutil
import urllib
import json
import requests
import subprocess
from errata_tool import ErrataConnector

from doozerlib import assembly, model, util as doozerutil
from pyartcd import exectools, constants
from pyartcd.oc import get_release_image_pullspec, extract_release_binary, extract_release_client_tools

logger = logging.getLogger(__name__)
goArches = ["amd64", "s390x", "ppc64le", "arm64", "multi"]


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


def is_greenwave_all_pass_on_advisory(advisory_id: int) -> bool:
    """
    Use /api/v1/external_tests API to check if builds on advisory have failed greenwave_cvp test
    If the tests all pass then the data field of the return value will be empty
    Return True, If all greenwave test passed on advisory
    Return False, If there are failed test on advisory
    """
    logger.info(f"Check failed greenwave tests on {advisory_id}")
    result = ErrataConnector()._get(f'/api/v1/external_tests?filter[test_type]=greenwave_cvp&filter[status]=FAILED&filter[active]=true&page[size]=1000&filter[errata_id]={advisory_id}')
    if result.get('data', []):
        logger.warning(f"Some greenwave tests on {advisory_id} failed with {result}")
        return False
    return True


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


async def load_releases_config(build_data_path: os.PathLike) -> Optional[Dict]:
    try:
        async with aiofiles.open(Path(build_data_path) / "releases.yml", "r") as f:
            content = await f.read()
        return yaml.safe_load(content)
    except FileNotFoundError:
        return None


def get_assembly_type(releases_config: Dict, assembly_name: str):
    return assembly.assembly_type(model.Model(releases_config), assembly_name)


def get_assembly_basis(releases_config: Dict, assembly_name: str):
    return assembly.assembly_basis(model.Model(releases_config), assembly_name)


def get_assembly_promotion_permits(releases_config: Dict, assembly_name: str):
    return assembly._assembly_config_struct(model.Model(releases_config), assembly_name, 'promotion_permits', [])


def get_release_name_for_assembly(group_name: str, releases_config: Dict, assembly_name: str):
    return doozerutil.get_release_name_for_assembly(group_name, model.Model(releases_config), assembly_name)


def is_rpm_pinned(releases_config: Dict, assembly_name: str, rpm_name: str):
    pinned_rpms = assembly._assembly_config_struct(model.Model(releases_config), assembly_name, 'members', {'rpms': []})['rpms']
    return any(rpm['distgit_key'] == rpm_name for rpm in pinned_rpms)


async def kinit():
    logger.info('Initializing ocp-build kerberos credentials')

    keytab_file = os.getenv('DISTGIT_KEYTAB_FILE', None)
    keytab_user = os.getenv('DISTGIT_KEYTAB_USER', 'exd-ocp-buildvm-bot-prod@IPA.REDHAT.COM')
    if keytab_file:
        # The '-f' ensures that the ticket is forwarded to remote hosts
        # when using SSH. This is required for when we build signed
        # puddles.
        cmd = [
            'kinit',
            '-f',
            '-k',
            '-t',
            keytab_file,
            keytab_user
        ]
        await exectools.cmd_assert_async(cmd)
    else:
        logger.warning('DISTGIT_KEYTAB_FILE is not set. Using any existing kerberos credential.')


async def branch_arches(group: str, assembly: str, ga_only: bool = False) -> list:
    """
    Find the supported arches for a specific release
    :param str group: The name of the branch to get configs for. For example: 'openshift-4.12
    :param str assembly: The name of the assembly. For example: 'stream'
    :param bool ga_only: If you only want group arches and do not care about arches_override.
    :return: A list of the arches built for this branch
    """

    logger.info('Fetching group config for %s', group)
    group_config = await load_group_config(group=group, assembly=assembly)

    # Check if arches_override has been specified. This is used in group.yaml
    # when we temporarily want to build for CPU architectures that are not yet GA.
    arches_override = group_config.get('arches_override', None)
    if arches_override and ga_only:
        return arches_override

    # Otherwise, read supported arches from group config
    return group_config['arches']


def get_changes(yaml_data: dict) -> dict:
    """
    Scans data outputted by config:scan-sources yaml and records changed
    elements in the object it returns.
    The return dict has optional .rpms, .images and .rhcos fields,
    that are omitted if no change was detected.
    """

    changes = {}

    rpms = [rpm['name'] for rpm in yaml_data['rpms'] if rpm['changed']]
    if rpms:
        changes['rpms'] = rpms

    images = [image['name'] for image in yaml_data['images'] if image['changed']]
    if images:
        changes['images'] = images

    rhcos = [rhcos['name'] for rhcos in yaml_data['rhcos'] if rhcos['changed']]
    if rhcos:
        changes['rhcos'] = rhcos

    return changes


async def get_freeze_automation(version: str, data_path: str = constants.OCP_BUILD_DATA_URL,
                                doozer_working: str = '') -> str:
    """
    Returns freeze_automation flag for a specific group
    """

    cmd = [
        'doozer',
        f'--working-dir={doozer_working}' if doozer_working else '',
        '--assembly=stream',
        f'--data-path={data_path}',
        f'--group=openshift-{version}',
        'config:read-group',
        '--default=no',
        'freeze_automation'
    ]
    _, out, _ = await exectools.cmd_gather_async(cmd)
    return out.strip()


def is_manual_build() -> bool:
    """
    Builds that are triggered manually by a Jenkins user carry a BUILD_USER_EMAIL environment variable.
    If this var is not defined, we can infer that the build was triggered by a timer.

    Be aware that Jenkins pipeline need to pass this var by enclosing the code in a wrap([$class: 'BuildUser']) {} block
    """

    build_user_email = os.getenv('BUILD_USER_EMAIL')
    logger.info('Found BUILD_USER_EMAIL=%s', build_user_email)

    if build_user_email is not None:
        logger.info('Considering this a manual build')
        return True

    logger.info('Considering this a scheduled build')
    return False


async def is_build_permitted(version: str, data_path: str = constants.OCP_BUILD_DATA_URL,
                             doozer_working: str = '') -> bool:
    """
    Check whether the group should be built right now.
    This depends on:
        - group config 'freeze_automation'
        - manual/scheduled run
        - current day of the week
    """

    # Get 'freeze_automation' flag
    freeze_automation = await get_freeze_automation(version, data_path, doozer_working)
    logger.info('Group freeze automation flag is set to: "%s"', freeze_automation)

    # Check for frozen automation
    # yaml parses unquoted "yes" as a boolean... accept either
    if freeze_automation in ['yes', 'True']:
        logger.info('All automation is currently disabled by freeze_automation in group.yml.')
        return False

    # Check for frozen scheduled automation
    if freeze_automation == "scheduled" and not is_manual_build():
        logger.info('Only manual runs are permitted according to freeze_automation in group.yml '
                    'and this run appears to be non-manual.')
        return False

    # Check if group can run on weekends
    if freeze_automation == 'weekdays':
        # Manual builds are always permitted
        if is_manual_build():
            logger.info('Current build is permitted as it has been triggered manually')
            return True

        # Check current day of the week
        weekday = datetime.today().strftime("%A")
        if weekday in ['Saturday', 'Sunday']:
            logger.info('Automation is permitted during weekends, and today is %s', weekday)
            return True

        logger.info('Scheduled builds for %s are permitted only on weekends, and today is %s', version, weekday)
        return False

    # Fallback to default
    return True


def getReleaseControllerArch(releaseStreamName):
    arch = 'amd64'
    streamNameComponents = releaseStreamName.split('-')
    for goArch in goArches:
        if goArch in streamNameComponents:
            arch = goArch
    return arch


def getReleaseControllerURL(releaseStreamName):
    arch = getReleaseControllerArch(releaseStreamName)
    return f"https://{arch}.ocp.releases.ci.openshift.org"


def stagePublishClient(working_dir, from_release_tag, release_name, arch, client_type):
    subprocess.run(f"docker login -u openshift-release-dev+art_quay_dev -p {os.environ['PASSWORD']} quay.io")
    minor = release_name.split(".")[1]
    quay_url = constants.QUAY_URL
    # Anything under this directory will be sync'd to the mirror
    BASE_TO_MIRROR_DIR = f"{working_dir}/to_mirror/openshift-v4"
    shutil.rmtree(BASE_TO_MIRROR_DIR, ignore_errors=True)

    # From the newly built release, extract the client tools into the workspace following the directory structure
    # we expect to publish to mirror
    CLIENT_MIRROR_DIR = f"{BASE_TO_MIRROR_DIR}/{arch}/clients/{client_type}/{release_name}"
    os.makedirs(CLIENT_MIRROR_DIR)

    if arch == 'x86_64':
        # oc image  extract requires an empty destination directory. So do this before extracting tools.
        # oc adm release extract --tools does not require an empty directory.
        image_stat, oc_mirror_pullspec = get_release_image_pullspec(f"{quay_url}:{from_release_tag}", "oc-mirror")
        if image_stat == 0:  # image exist
            # extract image to workdir, if failed it will raise error in function
            extract_release_binary(oc_mirror_pullspec, f"--path=/usr/bin/oc-mirror:{CLIENT_MIRROR_DIR}")
            # archive file
            with tarfile.open(f"{CLIENT_MIRROR_DIR}/oc-mirror.tar.gz", "w:gz") as tar:
                tar.add(f"{CLIENT_MIRROR_DIR}/oc-mirror")
            # calc shasum
            with open(f"{CLIENT_MIRROR_DIR}/oc-mirror", 'rb') as f:
                shasum = hashlib.sha256(f.read()).hexdigest()
            # write shasum to sha256sum.txt
            with open(f"{CLIENT_MIRROR_DIR}/sha256sum.txt", 'a') as f:
                f.write(shasum)
            # remove oc-mirror
            os.remove(f"{CLIENT_MIRROR_DIR}/oc-mirror")

    # extract release clients tools
    extract_release_client_tools(f"{quay_url}:{from_release_tag}", f"--to={CLIENT_MIRROR_DIR}", None)
    # create symlink for clients
    create_symlink(CLIENT_MIRROR_DIR, False, False)

    if minor > 0:
        try:
            # To encourage customers to explore dev-previews & pre-GA releases, populate changelog
            # https://issues.redhat.com/browse/ART-3040
            prevMinor = minor - 1
            rcURL = getReleaseControllerURL(release_name)
            rcArch = getReleaseControllerArch(release_name)
            stableStream = "4-stable" if rcArch == "amd64" else f"4-stable-{rcArch}"
            outputDest = f"{CLIENT_MIRROR_DIR}/changelog.html"
            outputDestMd = f"{CLIENT_MIRROR_DIR}/changelog.md"

            # If the previous minor is not yet GA, look for the latest fc/rc/ec. If the previous minor is GA, this should
            # always return 4.m.0.
            url = 'https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/4-stable/latest'
            full_url = f"{url}?{urllib.parse.urlencode({'in': f'=>4.{prevMinor}.0-0 <4.{prevMinor}.1'})}"
            with urllib.request.urlopen(full_url) as response:
                data = json.load(response)
            prevGA = data['name']
            # See if the previous minor has GA'd yet; e.g. https://amd64.ocp.releases.ci.openshift.org/releasestream/4-stable/release/4.8.0
            check = requests.get(f"{rcURL}/releasestream/{stableStream}/release/{prevGA}", timeout=30)
            if check.status_code == 200:
                # If prevGA is known to the release controller, compute the changelog html
                response = requests.get(f"{rcURL}/changelog?from={prevGA}&to={release_name}&format=html", timeout=180)
                with open(outputDest, 'w') as f:
                    f.write(response.text)
                # Also collect the output in markdown for SD to consume
                response = requests.get(f"{rcURL}/changelog?from={prevGA}&to={release_name}", timeout=180)
                with open(outputDestMd, 'w') as f:
                    f.write(response.text)
            else:
                with open(outputDest, 'w') as f:
                    f.write(f"<html><body><p>Changelog information cannot be computed for this release. Changelog information will be populated for new releases once {prevGA} is officially released.</p></body></html>")
                with open(outputDestMd, 'w') as f:
                    f.write(f"Changelog information cannot be computed for this release. Changelog information will be populated for new releases once {prevGA} is officially released.")
        except Exception as e:
            logger.error("Error generating changelog for release")
            raise e

    # extract opm binaries
    operator_registry = get_release_image_pullspec(f"{quay_url}:{from_release_tag}", "operator-registry")
    binaries = ['opm']
    platforms = ['linux']
    if arch == 'x86_64':  # For x86_64, we have binaries for macOS and Windows
        binaries += ['darwin-amd64-opm', 'windows-amd64-opm']
        platforms += ['mac', 'windows']
    path_args = []
    for binary in binaries:
        path_args.append(f'--path=/usr/bin/registry/{binary}:{CLIENT_MIRROR_DIR}')
    extract_release_binary(operator_registry, path_args)
    # Compress binaries into tar.gz files and calculate sha256 digests
    os.chdir(CLIENT_MIRROR_DIR)
    for idx, binary in enumerate(binaries):
        platform = platforms[idx]
        os.chmod(binary, 0o755)
        with tarfile.open(f"opm-{platform}-{release_name}.tar.gz", "w:gz") as tar:  # archive file
            tar.add(binary)
        os.remove(binary)  # remove oc-mirror
        os.symlink(f'opm-{platform}-{release_name}.tar.gz', f'opm-{platform}.tar.gz')  # create symlink
        with open(binary, 'rb') as f:  # calc shasum
            shasum = hashlib.sha256(f.read()).hexdigest()
        with open("sha256sum.txt", 'a') as f:  # write shasum to sha256sum.txt
            f.write(shasum)

    print_dir_tree(CLIENT_MIRROR_DIR)  # print dir tree
    print_file_content(f"{CLIENT_MIRROR_DIR}/sha256sum.txt")  # print sha256sum.txt

    # Publish the clients to our S3 bucket.
    subprocess.run(f"aws s3 sync --no-progress --exact-timestamps {BASE_TO_MIRROR_DIR}/ s3://art-srv-enterprise/pub/openshift-v4/", shell=True, check=True)


def stagePublishMultiClient(working_dir, from_release_tag, release_name, client_type):
    subprocess.run(f"docker login -u openshift-release-dev+art_quay_dev -p {os.environ['PASSWORD']} quay.io")
    # Anything under this directory will be sync'd to the mirror
    BASE_TO_MIRROR_DIR = f"{working_dir}/to_mirror/openshift-v4"
    shutil.rmtree(BASE_TO_MIRROR_DIR, ignore_errors=True)
    RELEASE_MIRROR_DIR = f"{BASE_TO_MIRROR_DIR}/multi/clients/{client_type}/{release_name}"

    for goArch in goArches:
        if goArch == "multi":
            continue
        # From the newly built release, extract the client tools into the workspace following the directory structure
        # we expect to publish to mirror
        CLIENT_MIRROR_DIR = f"{RELEASE_MIRROR_DIR}/{goArch}"
        os.makedirs(CLIENT_MIRROR_DIR)
        # extract release clients tools
        extract_release_client_tools(f"{constants.QUAY_URL}:{from_release_tag}", f"--to={CLIENT_MIRROR_DIR}", goArch)
        # create symlink for clients
        create_symlink(CLIENT_MIRROR_DIR, True, True)

    # Create a master sha256sum.txt including the sha256sum.txt files from all subarches
    # This is the file we will sign -- trust is transitive to the subarches
    subprocess.run(f"cd {RELEASE_MIRROR_DIR};sha256sum */sha256sum.txt > {RELEASE_MIRROR_DIR}/sha256sum.txt", shell=True, check=True)

    # Publish the clients to our S3 bucket.
    subprocess.run(f"aws s3 sync --no-progress --exact-timestamps {BASE_TO_MIRROR_DIR}/ s3://art-srv-enterprise/pub/openshift-v4/", shell=True, check=True)


def print_dir_tree(path_to_dir):
    for child in os.listdir(path_to_dir):
        child_path = os.path.join(path_to_dir, child)
        logger.info(child_path)


def print_file_content(path_to_file):
    with open(path_to_file, 'r') as f:
        logger.info(f.read())


def create_symlink(path_to_dir, print_tree, print_file):
    # External consumers want a link they can rely on.. e.g. .../latest/openshift-client-linux.tgz .
    # So whatever we extract, remove the version specific info and make a symlink with that name.
    for f in os.listdir(path_to_dir):
        if f.endswith(('.tar.gz', '.bz', '.zip', '.tgz')):
            # Is this already a link?
            if os.path.islink(f):
                continue
            # example file names:
            #  - openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
            #  - openshift-client-mac-4.3.0-0.nightly-2019-12-06-161135.tar.gz
            #  - openshift-install-mac-4.3.0-0.nightly-2019-12-06-161135.tar.gz
            #  - openshift-client-linux-4.1.9.tar.gz
            #  - openshift-install-mac-4.3.0-0.nightly-s390x-2020-01-06-081137.tar.gz
            #  ...
            # So, match, and store in a group, any character up to the point we find -DIGIT. Ignore everything else
            # until we match (and store in a group) one of the valid file extensions.
            match = re.match(r'^([^-]+)((-[^0-9][^-]+)+)-[0-9].*(tar.gz|tgz|bz|zip)$', f)
            if match:
                new_name = match.group(1) + match.group(2) + '.' + match.group(4)
                # Create a symlink like openshift-client-linux.tgz => openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
                os.symlink(f, new_name)

        if print_tree:
            print_dir_tree(path_to_dir)  # print dir tree
        if print_file:
            print_file_content(f"{path_to_dir}/sha256sum.txt")  # print sha256sum.txt

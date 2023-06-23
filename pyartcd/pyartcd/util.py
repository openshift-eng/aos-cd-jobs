import logging
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import aiofiles
import yaml
from doozerlib import assembly, model
from doozerlib import util as doozerutil
from errata_tool import ErrataConnector

from pyartcd import constants, exectools, jenkins

logger = logging.getLogger(__name__)


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


async def load_group_config(group: str, assembly: str, env=None,
                            doozer_data_path: str = constants.OCP_BUILD_DATA_URL,
                            doozer_data_gitref: str = '') -> Dict:
    if doozer_data_gitref:
        group += f'@{doozer_data_gitref}'
    cmd = [
        "doozer",
        f"--data-path={doozer_data_path}",
        "--group", group,
        "--assembly", assembly,
        "config:read-group",
        "--yaml",
    ]
    if env is None:
        env = os.environ.copy()
    temp_workdir = None
    if not env.get("DOOZER_WORKING_DIR"):
        temp_workdir = tempfile.mkdtemp(prefix="doozer-working-", dir=".")
        env["DOOZER_WORKING_DIR"] = temp_workdir
    try:
        _, stdout, _ = await exectools.cmd_gather_async(cmd, stderr=None, env=env)
    finally:
        if temp_workdir:
            shutil.rmtree(temp_workdir)
    group_config = yaml.safe_load(stdout)
    if not isinstance(group_config, dict):
        raise ValueError("ocp-build-data contains invalid group config.")
    return group_config


async def load_releases_config(group: str, data_path: str = constants.OCP_BUILD_DATA_URL) -> Optional[Dict]:
    cmd = [
        'doozer',
        f'--data-path={data_path}',
        f'--group={group}',
        'config:read-releases',
        '--yaml'
    ]

    try:
        _, out, _ = await exectools.cmd_gather_async(cmd)
        return yaml.safe_load(out.strip())

    except ChildProcessError as e:
        logger.error('Command "%s" failed: %s', ' '.join(cmd), e)
        return None


async def load_assembly(group: str, assembly: str, key: str = '',
                        data_path: str = constants.OCP_BUILD_DATA_URL) -> Optional[Dict]:
    cmd = [
        'doozer',
        f'--data-path={data_path}',
        f'--group={group}',
        'config:read-assembly',
        f'--assembly={assembly}',
        '--yaml',
        key
    ]

    try:
        _, out, _ = await exectools.cmd_gather_async(cmd)
        return yaml.safe_load(out.strip())

    except ChildProcessError as e:
        logger.error('Command "%s" failed: %s', ' '.join(cmd), e)
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
                                doozer_working: str = '', doozer_data_gitref: str = '') -> str:
    """
    Returns freeze_automation flag for a specific group
    """

    group_param = f'--group=openshift-{version}'
    if doozer_data_gitref:
        group_param += f'@{doozer_data_gitref}'

    cmd = [
        'doozer',
        f'--working-dir={doozer_working}' if doozer_working else '',
        '--assembly=stream',
        f'--data-path={data_path}',
        group_param,
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
                             doozer_working: str = '', doozer_data_path: str = '') -> bool:
    """
    Check whether the group should be built right now.
    This depends on:
        - group config 'freeze_automation'
        - manual/scheduled run
        - current day of the week
    """

    # Get 'freeze_automation' flag
    freeze_automation = await get_freeze_automation(version, data_path, doozer_working, doozer_data_path)
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


def log_dir_tree(path_to_dir):
    logger.info(f"Printing dir tree of {path_to_dir}")
    for child in os.listdir(path_to_dir):
        child_path = os.path.join(path_to_dir, child)
        logger.info(child_path)


def log_file_content(path_to_file):
    logger.info(f"Printing file content of {path_to_file}")
    with open(path_to_file, 'r') as f:
        logger.info(f.read())


async def sync_images(version: str, assembly: str, operator_nvrs: list,
                      doozer_data_path: str = constants.OCP_BUILD_DATA_URL, doozer_data_gitref: str = ''):
    """
    Run an image sync after a build. This will mirror content from internal registries to quay.
    After a successful sync an image stream is updated with the new tags and pullspecs.
    Also update the app registry with operator manifests.
    If operator_nvrs is given, will only build manifests for specified operator NVRs.
    If builds don't succeed, email and set result to UNSTABLE.
    """

    if assembly == 'test':
        logger.warning('Skipping build-sync job for test assembly')
    else:
        jenkins.start_build_sync(
            build_version=version,
            assembly=assembly,
            doozer_data_path=doozer_data_path,
            doozer_data_gitref=doozer_data_gitref
        )

    if operator_nvrs:
        jenkins.start_olm_bundle(
            build_version=version,
            assembly=assembly,
            operator_nvrs=operator_nvrs,
            doozer_data_path=doozer_data_path,
            doozer_data_gitref=doozer_data_gitref
        )

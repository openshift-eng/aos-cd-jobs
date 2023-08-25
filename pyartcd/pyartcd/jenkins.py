import functools
import logging
import os
import time
from enum import Enum
from typing import Optional

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.job import Job
from jenkinsapi.queue import QueueItem
from jenkinsapi.build import Build
from jenkinsapi.utils.crumb_requester import CrumbRequester

from pyartcd import constants

logger = logging.getLogger(__name__)

current_build_url = None
current_job_name = None
jenkins_client: Optional[Jenkins] = None


class Jobs(Enum):
    BUILD_SYNC = 'aos-cd-builds/build%2Fbuild-sync'
    BUILD_MICROSHIFT = 'aos-cd-builds/build%2Fbuild-microshift'
    OCP4 = 'aos-cd-builds/build%2Focp4'
    RHCOS = 'aos-cd-builds/build%2Frhcos'
    OLM_BUNDLE = 'aos-cd-builds/build%2Folm_bundle'
    SYNC_FOR_CI = 'scheduled-builds/sync-for-ci'
    MICROSHIFT_SYNC = 'aos-cd-builds/build%2Fmicroshift_sync'
    SCAN_OSH = 'aos-cd-builds/build%2Fscan-osh'


def init_jenkins():
    global jenkins_client
    if jenkins_client:
        return
    logger.info('Initializing Jenkins client..')
    requester = CrumbRequester(
        username=os.environ['JENKINS_SERVICE_ACCOUNT'],
        password=os.environ['JENKINS_SERVICE_ACCOUNT_TOKEN'],
        baseurl=constants.JENKINS_SERVER_URL
    )

    jenkins_client = Jenkins(
        constants.JENKINS_SERVER_URL,
        username=os.environ['JENKINS_SERVICE_ACCOUNT'],
        password=os.environ['JENKINS_SERVICE_ACCOUNT_TOKEN'],
        requester=requester,
        lazy=True
    )
    logger.info('Connected to Jenkins %s', jenkins_client.version)


def check_env_vars(func):
    """
    Enforces that BUILD_URL and JOB_NAME are set
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        global current_build_url, current_job_name
        current_build_url = current_build_url or os.environ.get('BUILD_URL', None)
        current_job_name = current_job_name or os.environ.get('JOB_NAME', None)

        if not current_build_url or not current_job_name:
            logger.error('Env vars BUILD_URL and JOB_NAME must be defined!')
            raise RuntimeError

        return func(*args, **kwargs)

    return wrapped


@check_env_vars
def wait_until_building(queue_item: QueueItem, job: Job, delay: int = 5) -> Build:
    """
    Watches a queue item and blocks until the scheduled build starts.
    Updates the description of the new build with the details of the caller job
    Returns a jenkinsapi.build.Build object representing the new build.
    """

    while True:
        try:
            data: dict = queue_item.poll()
            build_number = data['executable']['number']
            break
        except (KeyError, TypeError):
            logger.info('Build not started yet, sleeping for %s seconds...', delay)
            time.sleep(delay)

    triggered_build_url = f"{data['task']['url']}{build_number}"
    logger.info('Started new build at %s', triggered_build_url)

    # Update the description of the new build with the details of the caller job
    triggered_build_url = triggered_build_url.replace(constants.JENKINS_UI_URL, constants.JENKINS_SERVER_URL)
    triggered_build = Build(url=triggered_build_url, buildno=get_build_number(triggered_build_url), job=job)
    description = f'Started by upstream project <b>{current_job_name}</b> ' \
                  f'build number <a href="{current_build_url}">{get_build_number(current_build_url)}</a><br><br>'
    set_build_description(triggered_build, description)

    return triggered_build


def get_build_number(build_url: str) -> int:
    return int(list(filter(None, build_url.split('/')))[-1])


def set_build_description(build: Build, description: str):
    build.job.jenkins.requester.post_and_confirm_status(
        f'{build.baseurl}/submitDescription',
        params={
            'Submit': 'submit',
            'description': description
        },
        data="",
        valid=[200]
    )


@check_env_vars
def start_build(job: Jobs, params: dict,
                block_until_building: bool = True,
                block_until_complete: bool = False,
                watch_building_delay: int = 5) -> Optional[str]:
    """
    Starts a new Jenkins build

    :param job: one of Jobs enum
    :param params: a key-value collection to be passed to the build
    :param block_until_building: True by default. Will block until the new build starts. This ensures
        triggered jobs are properly backlinked to parent jobs.
    :param block_until_complete: False by default. Will block until the new build completes
    :param watch_building_delay: Poll rate for building state

    Returns the build result if block_until_complete is True, None otherwise
    """

    init_jenkins()
    job_name = job.value
    logger.info('Starting new build for job: %s', job_name)
    job = jenkins_client.get_job(job_name)
    queue_item = job.invoke(build_params=params)

    if not (block_until_building or block_until_complete):
        logger.info('Queued new build for job: %s', job_name)
        return

    # Wait for the build to start
    triggered_build = wait_until_building(queue_item, job, watch_building_delay)

    if not block_until_complete:
        return None

    # Wait for the build to complete; get its status and return it
    logger.info('Waiting for build to complete...')
    triggered_build.block_until_complete()
    result = triggered_build.poll()['result']
    logger.info('Build completed with result: %s', result)
    return result


def start_ocp4(build_version: str, assembly: str, rpm_list: list,
               image_list: list, **kwargs) -> Optional[str]:
    params = {
        'BUILD_VERSION': build_version,
        'ASSEMBLY': assembly
    }

    # If any rpm/image changed, force a build with only changed sources
    if rpm_list or image_list:
        params['PIN_BUILDS'] = True

    # Build only changed RPMs or none
    if rpm_list:
        params['BUILD_RPMS'] = 'only'
        params['RPM_LIST'] = ','.join(rpm_list)
    else:
        params['BUILD_RPMS'] = 'none'

    # Build only changed images or none
    if image_list:
        params['BUILD_IMAGES'] = 'only'
        params['IMAGE_LIST'] = ','.join(image_list)
    else:
        params['BUILD_IMAGES'] = 'none'

    return start_build(
        job=Jobs.OCP4,
        params=params,
        **kwargs
    )


def start_rhcos(build_version: str, new_build: bool, **kwargs) -> Optional[str]:
    return start_build(
        job=Jobs.RHCOS,
        params={'BUILD_VERSION': build_version, 'NEW_BUILD': new_build},
        **kwargs
    )


def start_build_sync(build_version: str, assembly: str, doozer_data_path: Optional[str] = None,
                     doozer_data_gitref: Optional[str] = None, **kwargs) -> Optional[str]:
    params = {
        'BUILD_VERSION': build_version,
        'ASSEMBLY': assembly,
    }
    if doozer_data_path:
        params['DOOZER_DATA_PATH'] = doozer_data_path
    if doozer_data_gitref:
        params['DOOZER_DATA_GITREF'] = doozer_data_gitref

    return start_build(
        job=Jobs.BUILD_SYNC,
        params=params,
        **kwargs
    )


def start_build_microshift(build_version: str, assembly: str, dry_run: bool, **kwargs) -> Optional[str]:
    return start_build(
        job=Jobs.BUILD_MICROSHIFT,
        params={
            'BUILD_VERSION': build_version,
            'ASSEMBLY': assembly,
            'DRY_RUN': dry_run
        },
        **kwargs
    )


def start_olm_bundle(build_version: str, assembly: str, operator_nvrs: list,
                     doozer_data_path: str = constants.OCP_BUILD_DATA_URL,
                     doozer_data_gitref: str = '', **kwargs) -> Optional[str]:
    if not operator_nvrs:
        logger.warning('Empty operator NVR received: skipping olm-bundle')
        return

    return start_build(
        job=Jobs.OLM_BUNDLE,
        params={
            'BUILD_VERSION': build_version,
            'ASSEMBLY': assembly,
            'DOOZER_DATA_PATH': doozer_data_path,
            'DOOZER_DATA_GITREF': doozer_data_gitref,
            'OPERATOR_NVRS': ','.join(operator_nvrs)
        },
        **kwargs
    )


def start_sync_for_ci(version: str, **kwargs):
    return start_build(
        job=Jobs.SYNC_FOR_CI,
        params={
            'ONLY_FOR_VERSION': version
        },
        **kwargs
    )


def start_microshift_sync(version: str, assembly: str, **kwargs):
    return start_build(
        job=Jobs.MICROSHIFT_SYNC,
        params={
            'BUILD_VERSION': version,
            'ASSEMBLY': assembly
        },
        **kwargs
    )


@check_env_vars
def update_title(title: str, append: bool = True):
    """
    Set build title to <title>. If append is True, retrieve current title,
    append <title> and update. Otherwise, replace current title
    """

    job = jenkins_client.get_job(current_job_name)
    build = Build(
        url=current_build_url.replace(constants.JENKINS_UI_URL, constants.JENKINS_SERVER_URL),
        buildno=int(list(filter(None, current_build_url.split('/')))[-1]),
        job=job
    )

    if append:
        title = build._data['displayName'] + title

    data = {'json': f'{{"displayName":"{title}"}}'}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Referer': f"{build.baseurl}/configure"}
    build.job.jenkins.requester.post_url(
        f'{build.baseurl}/configSubmit',
        params=data,
        data='',
        headers=headers)


@check_env_vars
def update_description(description: str, append: bool = True):
    """
    Set build description to <description>. If append is True, retrieve current description,
    append <description> and update. Otherwise, replace current description
    """

    job = jenkins_client.get_job(current_job_name)
    build = Build(
        url=current_build_url.replace(constants.JENKINS_UI_URL, constants.JENKINS_SERVER_URL),
        buildno=int(list(filter(None, current_build_url.split('/')))[-1]),
        job=job
    )

    if append:
        description = build.get_description() + description

    set_build_description(build, description)


def start_scan_osh(build_nvrs: str, email: Optional[str] = "", **kwargs):
    params = {
        'BUILD_NVRS': build_nvrs
    }

    if email:
        params['EMAIL'] = email

    return start_build(
        job=Jobs.SCAN_OSH,
        params=params,
        **kwargs
    )

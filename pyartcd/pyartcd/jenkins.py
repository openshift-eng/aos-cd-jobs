
import logging
import os
import time
from enum import Enum
from typing import Optional

from jenkinsapi.jenkins import Jenkins
from jenkinsapi.queue import QueueItem
from jenkinsapi.build import Build
from jenkinsapi.utils.crumb_requester import CrumbRequester

from pyartcd import constants

logger = logging.getLogger(__name__)


class Jobs(Enum):
    BUILD_SYNC = 'aos-cd-builds/build%2Fbuild-sync'
    BUILD_MICROSHIFT = 'aos-cd-builds/build%2Fbuild-microshift'
    OCP4 = 'aos-cd-builds/build%2Focp4'
    RHCOS = 'aos-cd-builds/build%2Frhcos'
    OLM_BUNDLE = 'aos-cd-builds/build%2Folm_bundle'


jenkins_client: Optional[Jenkins] = None


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


def block_until_building(queue_item: QueueItem, delay: int = 5) -> str:
    """
    Watches a queue item and blocks until the scheduled build starts.

    Returns the URL of the new build.
    """

    while True:
        try:
            data: dict = queue_item.poll()
            build_number = data['executable']['number']
            break
        except (KeyError, TypeError):
            logger.info('Build not started yet, sleeping for %s seconds...', delay)
            time.sleep(delay)

    logger.info('Build started: number = %s', build_number)
    return f"{data['task']['url']}{build_number}"


def start_build(job_name: str, params: dict, blocking: bool = False,
                watch_building_delay: int = 5) -> Optional[str]:
    """
    Starts a new Jenkins build

    :param job_name: e.g. "aos-cd-builds/build%2Fbuild-sync"
    :param params: a key-value collection to be passed to the build
    :param blocking: if True, will block until the new builds completes; if False,
                    start a new build in "fire-and-forget" fashion
    :param watch_building_delay: Poll rate for building state

    Returns the build result if blocking=True, None otherwise
    """

    init_jenkins()
    logger.info('Starting new build for job: %s', job_name)
    job = jenkins_client.get_job(job_name)
    queue_item = job.invoke(build_params=params)
    build_url = block_until_building(queue_item, watch_building_delay)
    logger.info('Started new build at %s', build_url)

    # Set build description to allow backlinking
    try:
        upstream_build_url = os.environ['BUILD_URL']
        job_name = os.environ['JOB_NAME']
    except KeyError:
        logger.error('BUILD_URL and JOB_NAME env vars must be defined!')
        raise

    upstream_build_number = list(filter(None, upstream_build_url.split('/')))[-1]
    build = Build(
        url=build_url.replace(constants.JENKINS_UI_URL, constants.JENKINS_SERVER_URL),
        buildno=int(build_url.split('/')[-1]),
        job=job
    )
    description = f'Started by upstream project <b>{job_name}</b> ' \
                  f'build number <a href="{upstream_build_url}">{upstream_build_number}</a><br><br>'
    build.job.jenkins.requester.post_and_confirm_status(
        f'{build.baseurl}/submitDescription',
        params={
            'Submit': 'submit',
            'description': description
        },
        data="",
        valid=[200]
    )

    # If blocking==True, wait for the build to complete; get its status and return it
    if blocking:
        logger.info('Waiting for build to complete...')
        build.block_until_complete()
        result = build.poll()['result']
        logger.info('Build completed with result: %s', result)
        return result


def start_ocp4(build_version: str, rpm_list: list = [], image_list: list = [], blocking: bool = False) -> Optional[str]:
    params = {'BUILD_VERSION': build_version}

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
        job_name=Jobs.OCP4.value,
        params=params,
        blocking=blocking
    )


def start_rhcos(build_version: str, new_build: bool, blocking: bool = False) -> Optional[str]:
    return start_build(
        job_name=Jobs.RHCOS.value,
        params={'BUILD_VERSION': build_version, 'NEW_BUILD': new_build},
        blocking=blocking
    )


def start_build_sync(build_version: str, assembly: str, doozer_data_path: Optional[str] = None,
                     doozer_data_gitref: Optional[str] = None, blocking: bool = False) -> Optional[str]:
    params = {
        'BUILD_VERSION': build_version,
        'ASSEMBLY': assembly,
    }
    if doozer_data_path:
        params['DOOZER_DATA_PATH'] = doozer_data_path
    if doozer_data_gitref:
        params['DOOZER_DATA_GITREF'] = doozer_data_gitref

    return start_build(
        job_name=Jobs.BUILD_SYNC.value,
        params=params,
        blocking=blocking
    )


def start_build_microshift(build_version: str, assembly: str, dry_run: bool, blocking: bool = False) -> Optional[str]:
    return start_build(
        job_name=Jobs.BUILD_MICROSHIFT.value,
        params={
            'BUILD_VERSION': build_version,
            'ASSEMBLY': assembly,
            'DRY_RUN': dry_run
        },
        blocking=blocking
    )


def start_olm_bundle(build_version: str, assembly: str, operator_nvrs: list,
                     doozer_data_path: str = constants.OCP_BUILD_DATA_URL,
                     doozer_data_gitref: str = '', blocking: bool = False) -> Optional[str]:
    if not operator_nvrs:
        logger.warning('Empty operator NVR received: skipping olm-bundle')
        return

    return start_build(
        job_name=Jobs.OLM_BUNDLE.value,
        params={
            'BUILD_VERSION': build_version,
            'ASSEMBLY': assembly,
            'DOOZER_DATA_PATH': doozer_data_path,
            'DOOZER_DATA_GITREF': doozer_data_gitref,
            'OPERATOR_NVRS': ','.join(operator_nvrs)
        },
        blocking=blocking
    )

import base64
import logging
import os
import aiohttp

logger = logging.getLogger(__name__)


async def trigger_jenkins_job(job_path: str, params=None):
    """
    Trigger a job using remote API calls.
    :param job_path: relative path to the job, starting from <buildvm hostname>:<jenkins port>
    :param params: optional dict containing job parameters
    """

    service_account = os.environ['JENKINS_SERVICE_ACCOUNT']
    token = os.environ['JENKINS_SERVICE_ACCOUNT_TOKEN']

    # Build authorization header
    auth = base64.b64encode(f'{service_account}:{token}'.encode()).decode()
    auth_header = f'Basic {auth}'
    headers = {'Authorization': auth_header}

    # Build url
    # If the job to be triggered is parametrized, use 'buildWithParameters' and send HTTP data
    # Otherwise, just call the 'build' endpoint with empty data
    url = f'https://buildvm.hosts.prod.psi.bos.redhat.com:8443/{job_path}'
    if params:
        url += '/buildWithParameters'
    else:
        url += '/build'

    # Call API endpoint
    logger.info('Triggering remote job /%s', job_path)
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url, data=params) as response:
            response.raise_for_status()
            await response.text()


async def trigger_ocp4(build_version: str):
    await trigger_jenkins_job(
        job_path='job/triggered-builds/job/ocp4',
        params={'BUILD_VERSION': build_version}
    )


async def trigger_rhcos(build_version: str, new_build: bool):
    await trigger_jenkins_job(
        job_path='job/triggered-builds/job/rhcos',
        params={'BUILD_VERSION': build_version, 'NEW_BUILD': new_build}
    )


async def trigger_build_sync(build_version: str):
    await trigger_jenkins_job(
        job_path='job/triggered-builds/job/build-sync',
        params={'BUILD_VERSION': build_version}
    )


async def trigger_build_microshift(build_version: str, assembly: str, dry_run: bool):
    await trigger_jenkins_job(
        job_path='job/triggered-builds/job/build-microshift',
        params={
            'BUILD_VERSION': build_version,
            'ASSEMBLY': assembly,
            'DRY_RUN': dry_run
        }
    )

"""
This module serves as an abstraction layer we can use to set title, description and status of builds.
Currently, builds run on Jenkins so we'll be using Jenkinsapi for this purpose.
In the future, we should adapt the abstraction to a new platform while keeping the interface intact.
"""

import functools
import logging
import os

from jenkinsapi.build import Build

from pyartcd import constants
from pyartcd import jenkins

logger = logging.getLogger(__name__)

build_url = os.environ.get('BUILD_URL', None)
job_name = os.environ.get('JOB_NAME', None)


def check_env_vars(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if not build_url or not job_name:
            logger.error('Env vars BUILD_URL and JOB_NAME must be defined!')
            raise RuntimeError
        return func(*args, **kwargs)

    return wrapped


@check_env_vars
def update_title(title: str, append: bool = True):
    """
    Set build title to <title>. If append is True, retrieve current title,
    append <title> and update. Otherwise, replace current title
    """

    job = jenkins.jenkins_client.get_job(job_name)
    build = Build(
        url=build_url.replace(constants.JENKINS_UI_URL, constants.JENKINS_SERVER_URL),
        buildno=int(list(filter(None, build_url.split('/')))[-1]),
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

    job = jenkins.jenkins_client.get_job(job_name)
    build = Build(
        url=build_url.replace(constants.JENKINS_UI_URL, constants.JENKINS_SERVER_URL),
        buildno=int(list(filter(None, build_url.split('/')))[-1]),
        job=job
    )

    if append:
        description = build.get_description() + description

    build.job.jenkins.requester.post_and_confirm_status(
        f'{build.baseurl}/submitDescription',
        params={
            'Submit': 'submit',
            'description': description
        },
        data="",
        valid=[200]
    )

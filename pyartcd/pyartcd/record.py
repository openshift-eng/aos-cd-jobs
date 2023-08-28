from typing import Dict, List, Optional, TextIO


def parse_record_log(file: TextIO) -> Dict[str, List[Dict[str, Optional[str]]]]:
    """
    Parse record.log from Doozer into a dict.
    The dict will be keyed by the type of operation performed.
    The values will be a list of dicts. Each of these dicts will contain the attributes for a single recorded operation of the top
    level key's type.
    """
    result = {}
    for line in file:
        fields = line.rstrip().split("|")
        type = fields[0]
        record = {entry_split[0]: entry_split[1] if len(entry_split) > 1 else None for entry_split in
                  map(lambda entry: entry.split("=", 1), fields[1:]) if entry_split[0]}
        result.setdefault(type, []).append(record)
    return result


def get_distgit_notify(record_log: dict) -> dict:
    """
    gets map of emails to notify from output of parse_record_log map formatted as below:

    rpms/jenkins-slave-maven-rhel7-docker
      source_alias: [source_alias map]
      image: openshift3/jenkins-slave-maven-rhel7
      dockerfile: /tmp/doozer-uEeF2_.tmp/distgits/jenkins-slave-maven-rhel7-docker/Dockerfile
      owners: bparees@redhat.com
      distgit: rpms/jenkins-slave-maven-rhel7-docker
      sha: 1b8903ef72878cd895b3f94bee1c6f5d60ce95c3    (NOT PRESENT ON FAILURE)
      failure: ....error description....      (ONLY PRESENT ON FAILURE)
    """

    result = {}

    # It's possible there were no commits or no one specified to notify
    if not record_log.get('distgit_commit', None):  # or not record_log.get('dockerfile_notify', None):
        return result

    source = record_log.get('source_alias', [])
    commit = record_log.get('distgit_commit', [])
    failure = record_log.get('distgit_commit_failure', [])
    notify = record_log.get('dockerfile_notify', [])

    # will use source alias to look up where Dockerfile came from
    source_alias = {}
    for i in range(len(source)):
        source_alias[source[i]['alias']] = source[i]

    # get notification emails by distgit name
    for i in range(len(notify)):
        notify[i]['source_alias'] = source_alias.get(notify[i]['source_alias'], {})
        result[notify[i]['distgit']] = notify[i]

    # match commit hash with notify email record
    for i in range(len(commit)):
        if result.get(commit[i]['distgit'], None):
            result[commit[i]['distgit']]['sha'] = commit[i]['sha']

    # OR see if the notification is for a merge failure
    for i in range(len(failure)):
        if result.get(failure[i]['distgit'], None):
            result[failure[i]['distgit']]['failure'] = failure[i]['message']

    return result


def get_failed_builds(record_log: dict, full_record: bool = False) -> dict:
    """
    Returns a map of distgit => task_url OR full record.log dict entry IFF the distgit's build failed
    """

    builds = record_log.get('build', [])
    failed_map = {}

    for build in builds:
        distgit = build['distgit']

        if build['status'] != '0':
            failed_map[distgit] = build if full_record else build['task_url']

        elif build['push_status'] != '0':
            failed_map[distgit] = build if full_record else 'Failed to push built image. See debug.log'

        else:
            # build may have succeeded later. If so, remove.
            if failed_map.get(distgit, None):
                del failed_map[distgit]

    return failed_map


def determine_build_failure_ratio(record_log: dict) -> dict:
    """
    Determine what the last build status was for each distgit.
    We're only interested in whether the build succeeded - ignore push failures.
    """

    last_status = {}
    for build in record_log.get('build', []):
        last_status[build['distgit']] = build['status']

    total = len(last_status)
    failed = len({distgit for distgit, status in last_status.items() if status != '0'})
    ratio = failed / total if total else 0

    return {'failed': failed, 'total': total, 'ratio': ratio}


def get_successful_builds(record_log: dict, full_record: bool = False) -> dict:
    """
    Returns a map of distgit => task_url OR full record.log dict entry IFF the distgit's build succeeded
    """

    builds = record_log.get('build', [])
    success_map = {}

    for build in builds:
        distgit = build['distgit']
        if build['status'] == '0':
            success_map[distgit] = build if full_record else build['task_url']

    return success_map


def get_successful_rpms(record_log: dict, full_record: bool = False) -> dict:
    """
    Returns a map of distgit => task_url OR full record.log dict entry IFF the distgit's build succeeded
    """

    rpms = record_log.get("build_rpm", [])
    success_map = {}

    for rpm in rpms:
        distgit = rpm["distgit_key"]
        if rpm["status"] == "0":
            success_map[distgit] = rpm if full_record else rpm["task_url"]

    return success_map

#!/usr/bin/env python

from datetime import datetime
from json import dump
from subprocess import check_output

from os import getenv, listdir
from os.path import join

timestamp = int((datetime.utcnow() - datetime(1970,1,1)).total_seconds())
node_name = check_output(["uname", "--nodename"]).strip()
jenkins_node_name = "ci.openshift"  # today only one master schedules jobs

repos = {}

repository_base_dir = "/data/src/github.com/openshift"
for repository in listdir(repository_base_dir):
    repository_dir = join(repository_base_dir, repository)

    version_info = ""
    repository_env_name = repository.upper().replace('-', '_')
    target_branch = getenv(repository_env_name + "_TARGET_BRANCH", "")
    if len(target_branch) > 0:
        target_branch_sha = check_output(
            ["git", "log", "-1", "--pretty=%H", "origin/{}".format(target_branch)],
            cwd=repository_dir
        ).strip()
        version_info += "{}:{}".format(target_branch, target_branch_sha)

    pull_id = getenv(repository_env_name + "_PULL_ID", "")
    if len(pull_id) > 0:
        pull_sha = check_output(
            ["git", "log", "-1", "--pretty=%H", "pull-{}".format(pull_id)],
            cwd=repository_dir
        ).strip()
        version_info += ",{}:{}".format(pull_id, pull_sha)

    if repository == "origin":
        # today we support PULL_REFS only for origin
        pull_refs = getenv("PULL_REFS", "")
        if len(pull_refs) > 0:
            version_info = pull_refs

    if len(version_info) >0:
        repos["openshift/{}".format(repository)] = version_info

version_script = """source hack/lib/init.sh
os::build::version::get_vars
echo -n "${OS_GIT_VERSION}"
"""

version_script_path = "/tmp/origin_version.sh"
with open(version_script_path, "w+") as version_script_file:
    version_script_file.write(version_script)

version = check_output(
    ["bash", version_script_path],
    cwd=join(repository_base_dir, "origin")
)

# we are following the k8s convention for the
# format and layout of this file so we can
# plug in to systems like Gubernator
with open("/data/started.json", "w+") as started_file:
    dump({
        "timestamp": timestamp,
        "node": node_name,
        "jenkins-node": jenkins_node_name,
        "pull": repos["openshift/origin"],
        "version": version,
        "repos": repos,
        "repo-version": version
    }, started_file)

#!/usr/bin/env python

from datetime import datetime
from json import dump, load
from urllib import urlopen

from os import getenv

timestamp = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())
with open("/data/started.json") as started_file:
    started_data = load(started_file)

result = load(urlopen("{}api/json".format(getenv("BUILD_URL"))))["result"]

# we are following the k8s convention for the
# format and layout of this file so we can
# plug in to systems like Gubernator
with open("/data/finished.json", "w+") as finished_file:
    dump({
        "timestamp": timestamp,
        "version": started_data["version"],
        "job-version": started_data["version"],
        "result": result,
        "passed": result == "SUCCESS",
        "metadata": {
            "repo": "{}/{}".format(getenv("REPO_OWNER", ""),getenv("REPO_NAME", "")),
            "repos": started_data["repos"],
            "repo_commit": getenv("PULL_PULL_SHA", "")
        }
    }, finished_file)
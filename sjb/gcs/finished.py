#!/usr/bin/env python

from datetime import datetime
from json import dump, load
from urllib import urlopen

result = load(urlopen("{}api/json".format(getenv("BUILD_URL"))))["result"]

# we are following the k8s convention for the
# format and layout of this file so we can
# plug in to systems like Gubernator
with open("/data/finished.json", "w+") as finished_file:
    dump({
        "timestamp": int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()),
        "result": result,
        "passed": result == "SUCCESS"
    }, finished_file)
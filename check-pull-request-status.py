#!/usr/bin/env python
from __future__ import print_function

import sys

from yaml import load
from github3 import login

if len(sys.argv) != 3:
    print("USAGE: {} PULL_REQUEST_ID CREDENTIAL_STORE".format(sys.argv[0]))
    exit(1)

pull_request_id = int(sys.argv[1])
credential_file = sys.argv[2]

with open(credential_file) as credential_store:
    credentials = load(credential_store)
    user = credentials['github.com'][0]['user']
    oauth_token = credentials['github.com'][0]['oauth_token']

client = login(token=oauth_token)

pull_request = client.pull_request(owner='openshift', repository='openshift-ansible', number=pull_request_id)
pull_request_statuses = client._json(client._get(pull_request.statuses_url.replace('statuses', 'status')), 200)['statuses']

blocking_statuses = [
    'aos-ci-jenkins/OS_3.5_NOT_containerized',
    'aos-ci-jenkins/OS_3.5_NOT_containerized_e2e_tests',
    'aos-ci-jenkins/OS_3.5_containerized',
    'aos-ci-jenkins/OS_3.5_containerized_e2e_tests',
    'aos-ci-jenkins/OS_unit_tests',
    'continuous-integration/travis-ci/pr'
]

found_statuses = {}

failed = False
for status in pull_request_statuses:
    if status['context'] not in blocking_statuses:
        continue

    print("INFO: Found status '{}' with state '{}'.".format(status['context'], status['state']))
    found_statuses[status['context']] = status

errors = []
for status in blocking_statuses:
    if status not in found_statuses:
        errors.append("Status '{}' is required but was not found on this pull request.".format(status))
    elif found_statuses[status]['state'] != 'success':
        errors.append("Status '{}' is in the '{}' state. This status must succeed for a merge.".format(status, found_statuses[status]['state']))

if len(errors) > 0:
    for error in errors:
        print('[ERROR] {}'.format(error))
    exit(1)
else:
    exit(0)

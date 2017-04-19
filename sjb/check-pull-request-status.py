#!/usr/bin/env python
from __future__ import print_function

import sys

from yaml import load
from github3 import login

if len(sys.argv) != 5:
    print("USAGE: {} PULL_REQUEST_ID OPENSHIFT_ANSIBLE_TARGET_BRANCH CREDENTIAL_STORE STATUS_CONFIG".format(sys.argv[0]))
    exit(1)

pull_request_id = int(sys.argv[1])
target_branch = sys.argv[2]
credential_file = sys.argv[3]
status_config_file = sys.argv[4]

with open(credential_file) as credential_store:
    credentials = load(credential_store)
    user = credentials['github.com'][0]['user']
    oauth_token = credentials['github.com'][0]['oauth_token']

client = login(token=oauth_token)

pull_request = client.pull_request(owner='openshift', repository='openshift-ansible', number=pull_request_id)
pull_request_statuses = client._json(client._get(pull_request.statuses_url.replace('statuses', 'status')), 200)['statuses']

blocking_statuses = []

with open(status_config_file) as status_config:
    config = load(status_config)
    if target_branch not in config:
        print("[ERROR] No GitHub PR statuses have been configured for branch '{}'.".format(target_branch))
        exit(1)
    blocking_statuses.extend(config[target_branch])
    blocking_statuses.extend(config["common_status"])

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

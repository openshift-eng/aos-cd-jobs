#!/usr/bin/env python3
from __future__ import print_function
import os
import time
import sys

import errata_tool


def rpmdiffs_ran(advisory):
    advisory.refresh()
    rpmdiffs = advisory.externalTests(test_type='rpmdiff')

    print("Checking to see if RPM diffs have finished running")
    print("Current RPM Diff status data:")
    not_finished_diffs = []
    for diff in rpmdiffs:
        print_diff(diff)
        if diff['attributes']['status'] in ['QUEUED_FOR_TEST', 'RUNNING', 'PENDING']:
            not_finished_diffs.append(diff)

    if not_finished_diffs:
        print("There are {} rpmdiffs which have not ran or completed yet".format(
            len(not_finished_diffs)))
        return False
    else:
        print("All diffs have finished running")
        return True

def rpmdiffs_resolved(advisory):
    advisory.refresh()
    rpmdiffs = advisory.externalTests(test_type='rpmdiff')
    completed_diffs = []
    incomplete_diffs = []
    failed_diffs = []

    print("Current RPM Diff status data:")

    for diff in rpmdiffs:
        print_diff(diff)
        if diff['attributes']['status'] in ['INFO', 'WAIVED', 'PASSED']:
            completed_diffs.append(diff)
        elif diff['attributes']['status'] in ['NEEDS_INSPECTION', 'FAILED']:
            failed_diffs.append(diff)
        else:
            incomplete_diffs.append(diff)

    if incomplete_diffs:
        pass
    elif failed_diffs:
        print("One or more RPM Diffs FAILED and require inspection")
        for diff in failed_diffs:
            print_diff(diff)
        # This will exit non-0 on its own after other checks
    else:
        print("All RPM diffs have been resolved")
        exit(0)

    for diff in incomplete_diffs:
        print_diff(diff)
    exit(1)

def print_diff(rpmdiff):
    url = "https://rpmdiff.engineering.redhat.com/run/{}/".format(
        rpmdiff['attributes']['external_id'])
    print("{status} - {nvr} - {url}".format(
        status=rpmdiff['attributes']['status'],
        nvr=rpmdiff['relationships']['brew_build']['nvr'],
        url=url))

def usage():
    print("""Usage: {} <command> ADVISORY
""".format(sys.argv[0]))
    print("""Advisory is an ADVISORY id number

commands:
    check-ran - Polls until all rpmdiffs have finished running
    check-resolved - Check if all rpmdiffs have been resovled
        Exits after checking once
""")

if __name__ == '__main__':
    if 'REQUESTS_CA_BUNDLE' not in os.environ:
        os.environ['REQUESTS_CA_BUNDLE'] = '/etc/pki/tls/certs/ca-bundle.crt'

    if len(sys.argv) != 3:
        usage()
        exit (1)
    elif sys.argv[1] == "-h" or sys.argv[1] == "--help":
        usage()
        exit (0)
    else:
        command = sys.argv[1]
        advisory = errata_tool.Erratum(errata_id=sys.argv[2])

    if command == 'check-ran':
        while not rpmdiffs_ran(advisory):
            print("Sleeping 60s and then polling again")
            time.sleep(60)
    elif command == 'check-resolved':
        rpmdiffs_resolved(advisory)
    else:
        print("Invalid command: {}".format(command))
        exit(1)

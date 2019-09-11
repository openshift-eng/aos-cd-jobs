#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import click
import subprocess
import shlex

RULE_COMMENT = "Rule managed by ART"
LOG_COMMENT = "Log rule managed by ART"
LOG_PREFIX_ALL_CONNECTION = "New Connection: "
LOG_PREFIX_DISALLOWED_CONNECTION = "Disallowed Connection: "


def make_output_args(cidr):
    return ['OUTPUT',
            '-d', cidr,
            '-j', 'ACCEPT',
            '-m', 'comment',
            '--comment', RULE_COMMENT
            ]


def make_output_log_args(prefix):
    return [
        'OUTPUT',
        '!', '-o', 'lo',  # Avoid logging loopback communication
        '-m', 'state',
        '--state', 'NEW',
        '-j', 'LOG',
        '--log-prefix', prefix,
        '-m', 'comment',
        '--comment', LOG_COMMENT
    ]

@click.command()
@click.option('-n', '--output-networks', metavar='FILE',
              multiple=True,
              help='File(s) with allowed cidr on each line',
              required=False,
              default=[])
@click.option('--dry-run', default=False, is_flag=True,
              help='Print what would have been done')
@click.option('--save', default=False, is_flag=True,
              help='Save resultant iptables configuration for next boot')
@click.option('--clean', default=False, is_flag=True,
              help='Clean out all rules installed by this program')
def main(output_networks, dry_run, save, clean):

    if (not clean and not output_networks) or (clean and output_networks):
        print('Either --output-networks XOR --clean is required')
        exit(1)

    # Read in the current state of iptables
    iptables_start = subprocess.check_output('iptables-save').strip().split('\n')

    print('There are presently {} iptable rules installed'.format(len(iptables_start)))

    parser = argparse.ArgumentParser(description='inner argpase for iptables argument parsing')
    parser.add_argument('-d', '--destination', default=None, help='The destination')

    # Maps cidr -> rule string
    iptables_output_map = {}
    logging_rules = []

    for rule in iptables_start:

        if not rule.strip().startswith('-'):
            continue

        rule_args = shlex.split(rule)
        parsed_args = parser.parse_known_args(rule_args)[0]

        if ' OUTPUT ' in rule:
            if parsed_args.destination and RULE_COMMENT in rule:
                iptables_output_map[parsed_args.destination] = rule
            elif LOG_COMMENT in rule:
                logging_rules.append(rule)

    print('There are {} OUTPUT rules under management'.format(len(iptables_output_map)))
    print('There are {} OUTPUT logging rules under management'.format(len(logging_rules)))

    cidr_set = set()
    # For each input file specified, add cidrs to the set
    for file in output_networks:
        with open(file, 'r') as f:
            for cidr in f.readlines():
                cidr = cidr.strip()

                # Skip empty lines
                if not cidr:
                    continue

                # Skip comments
                if cidr.startswith('#'):
                    continue

                cidr_set.add(cidr)

    for cidr in cidr_set:
        if cidr in iptables_output_map:
            # This rule is already mapped; ignore it
            print('Rule already present for {}'.format(cidr))
            del iptables_output_map[cidr]
            continue

        cmd = ['iptables', '-I']
        cmd.extend(make_output_args(cidr))

        if dry_run:
            print('Would have ADDED rule: {}'.format(cmd))
        else:
            print('Adding rule for: {}'.format(cidr))
            subprocess.check_output(cmd)

    # Remove old logging rules so we can re-insert them in the right locations
    for old_logging_rule in logging_rules:
        # During insertion / append into delete rule
        delete_it = old_logging_rule.replace('-I OUTPUT', '-D OUTPUT').replace('-A OUTPUT', '-D OUTPUT')
        cmd = ['iptables']
        cmd.extend(shlex.split(delete_it))

        if dry_run:
            print('Would have DELETED old logging rule: {}'.format(cmd))
        else:
            print('Deleting old logging rule')
            subprocess.check_output(cmd)

    if not clean:
        new_connection_cmd = [
            'iptables',
            '-I'  # Insert at the top of the chain
        ]
        new_connection_cmd.extend(make_output_log_args(LOG_PREFIX_ALL_CONNECTION))
        if dry_run:
            print('Would have added new connection LOG: {}'.format(new_connection_cmd))
        else:
            print('Adding new connection logging rule')
            subprocess.check_output(new_connection_cmd)

        disallowed_connection_cmd = [
            'iptables',
            '-A'  # Insert at the bottom of the chain
        ]
        disallowed_connection_cmd.extend(make_output_log_args(LOG_PREFIX_DISALLOWED_CONNECTION))
        if dry_run:
            print('Would have added disallowed connection LOG: {}'.format(disallowed_connection_cmd))
        else:
            print('Adding disallowed connection logging rule')
            subprocess.check_output(disallowed_connection_cmd)

    # Iterate through the remaining rules; they are old and should be removed
    for cidr in iptables_output_map:
        rule = iptables_output_map[cidr]
        delete_it = rule.replace('-I OUTPUT', '-D OUTPUT').replace('-A OUTPUT', '-D OUTPUT')
        cmd = [ 'iptables' ]
        cmd.extend(shlex.split(delete_it))

        if dry_run:
            print('Would have DELETED old rule: {}'.format(cmd))
        else:
            print('Deleting rule for: {}'.format(cidr))
            subprocess.check_output(cmd)

    if save:
        cmd = ['/sbin/service',
               'iptables',
               'save']

        if dry_run:
            print('Would have saved iptables with: {}'.format(cmd))
        else:
            print('Saving iptables configuration')
            subprocess.check_output(cmd)


if __name__ == '__main__':
    main()

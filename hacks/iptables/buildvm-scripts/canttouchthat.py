#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import click
import subprocess

LOG_PREFIX_ALL_CONNECTION = "New Connection: "
LOG_PREFIX_DISALLOWED_CONNECTION = "Disallowed Connection: "


def reload_permanent_rules():
    subprocess.check_output(['firewall-cmd', '--reload'])


def remove_permanent_rules():
    subprocess.check_output(['firewall-cmd',
                             '--permanent',
                             '--direct',
                             '--remove-rules',
                             'ipv4',
                             'filter',
                             'OUTPUT',
                             ])
    subprocess.check_output(['firewall-cmd',
                             '--permanent',
                             '--direct',
                             '--remove-rules',
                             'ipv6',
                             'filter',
                             'OUTPUT',
                             ])


def install_logging_rule(priority, space, prefix, dry_run):
    cmd = [
        'firewall-cmd',
        '--permanent',
        '--direct',
        '--add-rule',
        space,
        'filter',
        'OUTPUT', '{}'.format(priority),
        '!', '-o', 'lo',  # Avoid logging loopback communication
        '-m', 'state',
        '--state', 'NEW',
        '-j', 'LOG',
        '--log-prefix', '"{}"'.format(prefix),
    ]

    if dry_run:
        print('Would have run: {}'.format(cmd))
    else:
        print('Adding logging rule in {} with prefix \'{}\''.format(space, prefix))
        subprocess.check_output(cmd)


def install_drop_rule(priority, space, dry_run):
    cmd = [
        'firewall-cmd',
        '--permanent',
        '--direct',
        '--add-rule',
        space,
        'filter',
        'OUTPUT', '{}'.format(priority),
        '!', '-o', 'lo',  # Avoid logging loopback communication
        '-j', 'REJECT', '--reject-with', 'icmp-host-prohibited'
    ]

    if dry_run:
        print('Would have run: {}'.format(cmd))
    else:
        print('Adding default REJECT rule for {}'.format(space))
        subprocess.check_output(cmd)


@click.command(short_help="Manage OUTPUT rules using firewalld")
@click.option('-n', '--output-networks', metavar='FILE',
              multiple=True,
              help='File(s) with allowed cidr on each line',
              required=False,
              default=[])
@click.option('--enforce', default=False, is_flag=True,
              help='If specified, REJECT all other output')
@click.option('--dry-run', default=False, is_flag=True,
              help='Print what would have been done')
@click.option('--clean', default=False, is_flag=True,
              help='Clean out all rules installed by this program')
def main(output_networks, enforce, dry_run, clean):
    """Manage persistent outgoing connection network rules for the system.

One or more input files provided by '-n' are read and compared with
the current system state. The system is updated to match the given
rule sets. Existing rules are removed from the system if not present
in the input files, missing rules are added.

Example input format:

\b
    10.0.0.0/8
    224.0.0.0/4
    140.211.0.0/16
    140.82.112.0/20
    2001:db8:abcd:8000::/50
    2406:daff:8000::/40

By default rules are only added, they are not enforced. That is to
say, packets will not be dropped. If the `--enforce` option is given
then a catch-all `REJECT` rule is installed after all of the the
`ACCEPT` rules. Running this again without the `--enforce` option will
remove the `REJECT` rule, effectively opening up outgoing traffic once
again.

Running with `--clean` will remove all installed rules.
"""
    if (not clean and not output_networks) or (clean and output_networks):
        print('Either --output-networks XOR --clean is required')
        exit(1)

    if clean:
        if dry_run:
            print('Would have removed all permanent rules and reloaded')
        else:
            remove_permanent_rules()
            reload_permanent_rules()
        exit(0)

    if dry_run:
        print('Would have reset all permanent rules')
    else:
        print('Removing all existing permanent rules')
        remove_permanent_rules()

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

        space = 'ipv4'
        if ':' in cidr:  # e.g. XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX/32
            space = 'ipv6'

        cmd = [
            'firewall-cmd',
            '--permanent',
            '--direct',
            '--add-rule',
            space,
            'filter',
            'OUTPUT', '5',
            '-d', cidr,
            '-j', 'ACCEPT'
        ]

        if dry_run:
            print('Would have run: "{}"'.format(' '.join(cmd)))
        else:
            print('Adding rule for {}'.format(cidr))
            subprocess.check_output(cmd)

    for space in ['ipv4', 'ipv6']:
        install_logging_rule(0, space, LOG_PREFIX_ALL_CONNECTION, dry_run)
        install_logging_rule(10, space, LOG_PREFIX_DISALLOWED_CONNECTION, dry_run)
        if enforce:
            install_drop_rule(100, space, dry_run)

    if not dry_run:
        reload_permanent_rules()


if __name__ == '__main__':
    main()

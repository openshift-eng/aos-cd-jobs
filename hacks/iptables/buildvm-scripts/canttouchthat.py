#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import click
import subprocess
import requests
import traceback
import xml.etree.cElementTree as ET
from io import BytesIO

LOG_PREFIX_ALL_CONNECTION = "New Connection: "
LOG_PREFIX_DISALLOWED_CONNECTION = "Disallowed Connection: "
DIRECT_XML_PATH = '/etc/firewalld/direct.xml'


def reload_permanent_rules():
    subprocess.check_output(['firewall-cmd', '--reload'])


def get_direct_rules(space):
    """
    :param space: ipv4 or ipv6
    :return: A line delimited string showing all currently active direct rules
    """
    return subprocess.check_output(['firewall-cmd', '--direct', '--get-rules', space, 'filter', 'OUTPUT'])


def write_direct_rules(direct):
    """
    :param direct: The ET.Element to write to the direct configuration file
    :return: n/a
    """
    tree = ET.ElementTree(direct)
    tree.write(DIRECT_XML_PATH, encoding='utf-8', xml_declaration=True)


def print_direct_rules(direct):
    """
    :param direct: The ET.Element to print to stdout
    :return: n/a
    """
    f = BytesIO()
    tree = ET.ElementTree(direct)
    tree.write(f, encoding='utf-8', xml_declaration=True)
    print(f.getvalue())


def remove_permanent_rules():
    direct = ET.Element('direct')
    write_direct_rules(direct)


def add_logging_rule(direct_root, priority, space, prefix):
    # e.g.
    # <rule priority="0" table="filter" ipv="ipv4" chain="OUTPUT">'!' -o lo -m state --state NEW -j LOG --log-prefix '"New Connection: "'</rule>

    ET.SubElement(direct_root, 'rule',
                  priority=str(priority),
                  table='filter',
                  ipv=space,
                  chain='OUTPUT').text = "'!' -o lo  -m state --state NEW -j LOG --log-prefix '\"{}: \"'".format(prefix)


def add_drop_rule(direct_root, priority, space):
    # e.g.   <rule priority="100" table="filter" ipv="ipv4" chain="OUTPUT">'!' -o lo -j REJECT --reject-with icmp-host-prohibited</rule>
    ET.SubElement(direct_root, 'rule',
                  priority=str(priority),
                  table='filter',
                  ipv=space,
                  chain='OUTPUT').text = "'!' -o lo -j REJECT --reject-with icmp-host-prohibited"


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

One or more input files provided by '-n' used to update the current
direct firewall rules. Existing rules are removed from the system if not present
in the input files, missing rules are added.

In addition to '-n' files, all non-EC2 AWS services are added to the
permitted ranges. This allows us to use things like SimpleDB.

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

    try:
        # Generally we want to be able to access AWS services, but not all of EC2.
        # Recommended code here: https://docs.aws.amazon.com/general/latest/gr/aws-ip-ranges.html#aws-ip-download
        ip_ranges = requests.get('https://ip-ranges.amazonaws.com/ip-ranges.json').json()
        for list_name, field_name in [('prefixes', 'ip_prefix'), ("ipv6_prefixes", 'ipv6_prefix')]:
            ranges = ip_ranges[list_name]
            amazon_ips = [item[field_name] for item in ranges if item["service"] == "AMAZON"]
            ec2_ips = [item[field_name] for item in ranges if item["service"] == "EC2"]
            amazon_ips_less_ec2 = []

            for ip in amazon_ips:
                if ip not in ec2_ips:
                    amazon_ips_less_ec2.append(ip)

            print('Adding {} out of {} AWS service IP ranges from {}'.format(len(amazon_ips_less_ec2), len(ranges), list_name))
            for ip in amazon_ips_less_ec2:
                cidr_set.add(str(ip))
    except:
        traceback.print_exc()
        print('Error fetching AWS IP addresses. You may need to run --clean mode and then try this command again.')
        exit(1)

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

    # firewall-cmd direct rules are stored in xml format in DIRECT_XML_PATH
    direct = ET.Element('direct')
    """
    e.g.
    <?xml version="1.0" encoding="utf-8"?>
    <direct>
      <rule priority="5" table="filter" ipv="ipv4" chain="OUTPUT">-d 54.182.0.0/16 -j ACCEPT</rule>
      <rule priority="5" table="filter" ipv="ipv4" chain="OUTPUT">-d 52.119.206.0/23 -j ACCEPT</rule>
      <rule priority="5" table="filter" ipv="ipv4" chain="OUTPUT">-d 13.52.118.0/23 -j ACCEPT</rule>
      <rule priority="5" table="filter" ipv="ipv4" chain="OUTPUT">-d 52.95.100.0/22 -j ACCEPT</rule>
      ...
    </direct>
    """

    for cidr in cidr_set:
        space = 'ipv4'
        if ':' in cidr:  # e.g. XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX/32
            space = 'ipv6'

        ET.SubElement(direct, 'rule',
                      priority='5',
                      table='filter',
                      ipv=space,
                      chain='OUTPUT').text = '-d {} -j ACCEPT'.format(cidr)

    for space in ['ipv4', 'ipv6']:
        add_logging_rule(direct, 0, space, LOG_PREFIX_ALL_CONNECTION)
        add_logging_rule(direct, 10, space, LOG_PREFIX_DISALLOWED_CONNECTION)
        if enforce:
            # Install drop rules
            # '!', '-o', 'lo',  # Avoid logging loopback communication
            #         '-j', 'REJECT', '--reject-with', 'icmp-host-prohibited'

            add_drop_rule(direct, 100, space)

    if not dry_run:
        print('Updating direct rules {}'.format(DIRECT_XML_PATH))
        write_direct_rules(direct)
        reload_permanent_rules()
        print('Currently installed ipv4 rules:\n{}'.format(get_direct_rules('ipv4')))
        print('Currently installed ipv6 rules:\n{}'.format(get_direct_rules('ipv6')))
    else:
        print('Would have written the following direct rules to {}'.format(DIRECT_XML_PATH))
        print_direct_rules(direct)


if __name__ == '__main__':
    main()

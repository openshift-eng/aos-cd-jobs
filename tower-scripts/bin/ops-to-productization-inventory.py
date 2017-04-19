#!/usr/bin/env python
# pylint: disable=invalid-name
'''
A script to generate an openshift-ansible style inventory from the ops multi-inventory cache.

Since no arguments can be passed into a dynamic inventory, the following
environment variables must be set:

CLUSTERNAME="opstest"
VERSION="3.3"             # The OpenShift major version we are configuring.
'''

import json
import os
import sys

if not os.environ.has_key('CLUSTERNAME'):
    print "Environment variable 'CLUSTERNAME' not set. exiting..."
    sys.exit(1)

if not os.environ.has_key('VERSION'):
    print "Environment variable 'VERSION' not set. exiting..."
    sys.exit(1)

CLUSTER_NAME = os.environ['CLUSTERNAME']

OPS_INVENTORY = json.loads(open('/dev/shm/.ansible/tmp/multi_inventory.cache').read())

HOOK_PATH = os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "../upgrades/"))

def print_inventory():
    """ Print an openshift-ansible compatible inventory. """

    inventory = {}
    inventory["_meta"] = {}
    inventory["_meta"]["hostvars"] = {}

    # get all hosts
    inventory["all_hosts"] = OPS_INVENTORY['oo_clusterid_' + CLUSTER_NAME]

    # get masters
    inventory["masters"] = list(set(OPS_INVENTORY['oo_clusterid_' + CLUSTER_NAME]) & \
                                set(OPS_INVENTORY['oo_hosttype_master']))
    inventory["etcd"] = list(set(OPS_INVENTORY['oo_clusterid_' + CLUSTER_NAME]) & \
                             set(OPS_INVENTORY['oo_hosttype_master']))

    # get nodes
    inventory["nodes"] = list(set(OPS_INVENTORY['oo_clusterid_' + CLUSTER_NAME]) & \
                              set(OPS_INVENTORY['oo_hosttype_node']))

    # populate _meta
    for host in inventory["all_hosts"]:
        inventory["_meta"]["hostvars"][host] = OPS_INVENTORY["_meta"]["hostvars"][host]
        host_vars = inventory["_meta"]["hostvars"][host]
        host_vars['ansible_user'] = 'root'
        host_vars['deployment_type'] = 'openshift-enterprise'
        host_vars['openshift_release'] = 'v%s' % os.environ['VERSION']
        host_vars['openshift_ip'] = host_vars['oo_private_ip']
        host_vars['openshift_public_ip'] = host_vars['oo_public_ip']
        host_vars['openshift_hostname'] = host_vars['ec2_private_dns_name']
        host_vars['openshift_public_hostname'] = host_vars['ec2_public_dns_name']

    for host in inventory["masters"]:
        host_vars = inventory["_meta"]["hostvars"][host]
        host_vars['openshift_master_cluster_method'] = "native"
        host_vars['openshift_master_api_port'] = "443"
        host_vars['openshift_master_console_port'] = "443"

#        # Triggers a full system restart after master upgrade is complete:
#        host_vars['openshift_rolling_restart_mode'] = "system"
#
#        # Define our hooks to remove/add masters from the ELB and perform full yum updates:
#        host_vars['openshift_master_upgrade_pre_hook'] = os.path.join(HOOK_PATH, "master_upgrade_pre.yml")
#        host_vars['openshift_master_upgrade_hook'] = os.path.join(HOOK_PATH, "master_upgrade.yml")
#        host_vars['openshift_master_upgrade_post_hook'] = os.path.join(HOOK_PATH, "master_upgrade_post.yml")

    print json.dumps(inventory)

if __name__ == "__main__":
    print_inventory()

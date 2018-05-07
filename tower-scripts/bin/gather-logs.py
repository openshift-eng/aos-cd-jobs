#!/usr/bin/env python
"""
Gather Logs
"""
#pylint: disable=invalid-name

from __future__ import print_function

import argparse
import atexit
import datetime
import os
import shutil
import subprocess
import sys
import tarfile
from distutils.version import StrictVersion

from openshift_tools.inventory_clients.inventory_util import Cluster

def parse_args():
    """ parse args """

    parser = argparse.ArgumentParser(description='Gather logs from clusters',
                                     epilog='Example: %(prog)s -c prod-cluster')

    parser.add_argument('-c', '--cluster-id', required=True, help='the cluster to perform the operation on')
    parser.add_argument('node', nargs='*', default=None, help='Optional; Nodes to gather logs on')

    args = parser.parse_args()

    return args

def main():
    """ main function """

    args = parse_args()
    gather_logs = GatherLogs(args.cluster_id, args.node)
    gather_logs.main()

#pylint: disable=too-many-instance-attributes
class GatherLogs(object):
    """  Gather Logs """

    MASTER_SERVICES_310 = ["etcd"]
    MASTER_LOGS_310 = ["api", "controllers"]
    MASTER_SERVICES = ["atomic-openshift-master-api", "atomic-openshift-master-controllers", "etcd"]
    NODE_SERVICES = ["docker", "atomic-openshift-node", "dnsmasq", "openvswitch" "ovs-vswitchd" "ovsdb-server"]

    def __init__(self, cluster, node_list=None):
        """ init functions """

        self.cluster = Cluster(cluster)
        self.node_list = node_list

        # set up directory vars to help us out
        self.bin_dir = os.path.dirname(os.path.realpath(__file__))
        home_dir = os.path.realpath(os.path.join(os.environ['HOME']))
        aos_dir = os.path.realpath(os.path.join(os.environ['HOME'], 'aos-cd'))
        self.tmp_dir = os.path.realpath(os.path.join(aos_dir, 'tmp'))
        self.upgrade_log_path = os.path.realpath(os.path.join(home_dir, 'upgrade_logs', self.cluster.name))

        now_timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M')
        self.base_dir = "logs_{}_{}".format(self.cluster.name, now_timestamp)
        self.work_dir = os.path.realpath(os.path.join(self.tmp_dir, self.base_dir))
        self.logfile = os.path.realpath(os.path.join(self.work_dir, 'gather-logs.debug'))

        os.makedirs(self.work_dir)

    def atexit_cleanup(self):
        """ cleanup atexit """

        shutil.rmtree(self.work_dir)

    def main(self):
        """ main function of the class """

        atexit.register(self.atexit_cleanup)

        self.get_master_logs()

        if self.node_list:
            for node in self.node_list:
                self.get_node_logs(node)

        self.create_tar()

    def create_tar(self):
        ''' create the tar file or send it to stdout '''

        tarfile_basename = os.path.basename(self.work_dir)

        with tarfile.open(fileobj=sys.stdout, mode='w|gz') as tar_fd:
            tar_fd.add(self.work_dir, arcname=tarfile_basename)

    def write_to_logfile(self, msg, msg_type='INFO'):
        ''' print to stderr and to logfile '''

        print("{}: {}".format(msg_type, msg), file=sys.stderr)

        with open(self.logfile, "a") as lfile:
            lfile.write("{}: {}".format(msg_type, msg))

    @staticmethod
    def run_cmd(cmd, logfile_path=None, stdin=None):
        """ run a command and return output and return code """

        if logfile_path is not None:
            logfile = open(logfile_path, "w+")
            sout = logfile
            serr = subprocess.STDOUT
        else:
            logfile = None
            sout = subprocess.PIPE
            serr = subprocess.PIPE

        proc = subprocess.Popen(cmd, stdin=stdin, stdout=sout, stderr=serr)
        stdout, stderr = proc.communicate()

        if logfile_path is not None:
            logfile.close()

        return proc.returncode, stdout, stderr

    def get_master_logs(self):
        """ get master logs """

        self.write_to_logfile('Collecting logs from masters...')

        master_dir = os.path.join(self.work_dir, 'masters')
        report_dir = os.path.join(master_dir, 'reports')
        journal_dir = os.path.join(master_dir, 'journal')
        os.makedirs(journal_dir)
        os.makedirs(report_dir)

        # Check for verison to see what we need to do
        if StrictVersion(self.cluster.openshift_version['short']) >= StrictVersion('3.10'):
            master_log_dir = os.path.join(master_dir, 'master_logs')
            os.makedirs(master_log_dir)

            services_to_gather = GatherLogs.MASTER_SERVICES_310
            for service in GatherLogs.MASTER_LOGS_310:
                self.write_to_logfile("Gathering logs for '{}'".format(service))
                gather_cmd = ['autokeys_loader', 'opssh', '-c', self.cluster.name, '-t', 'master', '--outdir',
                              os.path.join(master_log_dir, service), "--errdir", os.path.join(master_log_dir, service),
                              "/usr/local/bin/master-logs {} {}".format(service, service)]

                GatherLogs.run_cmd(gather_cmd)
        else:
            services_to_gather = GatherLogs.MASTER_SERVICES

        for service in services_to_gather:
            self.write_to_logfile("Gathering logs for '{}'".format(service))
            gather_cmd = ['autokeys_loader', 'opssh', '-c', self.cluster.name, '-t', 'master', '--outdir',
                          os.path.join(journal_dir, service),
                          "journalctl --no-pager --since '2 days ago' -u {}.service".format(service)]

            GatherLogs.run_cmd(gather_cmd)

        self.write_to_logfile("Gathering node list and metrics")
        GatherLogs.run_cmd(['autokeys_loader', 'ossh', "root@{}".format(self.cluster.primary_master),
                            '-c', "oc get node"],
                           os.path.join(report_dir, 'nodes.txt'))

        GatherLogs.run_cmd(['autokeys_loader', 'ossh', "root@{}".format(self.cluster.primary_master),
                            '-c', "oc get --raw /metrics"],
                           os.path.join(report_dir, 'metrics.txt'))


    def get_node_logs(self, node):
        """ get node logs """

        inv_node = self.cluster.convert_os_to_inv_name(node)
        if inv_node is None:
            self.write_to_logfile("Node: '{}' Not Found!".format(node), 'WARNING')
            return 0

        node_dir = os.path.join(self.work_dir, 'nodes', inv_node, 'journal')

        os.makedirs(node_dir)

        for service in GatherLogs.NODE_SERVICES:
            self.write_to_logfile("Gathering Node logs for '{}'".format(service))
            gather_cmd = ['autokeys_loader', 'ossh', 'root@{}'.format(inv_node), '-c',
                          "journalctl --no-pager --since '2 days ago' -u {}.service".format(service)]

            GatherLogs.run_cmd(gather_cmd)

        self.write_to_logfile("Gathering node info and metrics")
        GatherLogs.run_cmd(['autokeys_loader', 'ossh', "root@{}".format(self.cluster.primary_master),
                            '-c', "oc get --raw /api/v1/nodes/{}/proxy/metrics".format(inv_node)],
                           os.path.join(node_dir, 'metrics.txt'))

        GatherLogs.run_cmd(['autokeys_loader', 'ossh', "root@{}".format(self.cluster.primary_master),
                            '-c', "oc describe node {}".format(inv_node)],
                           os.path.join(node_dir, 'describe.txt'))

if __name__ == '__main__':
    main()

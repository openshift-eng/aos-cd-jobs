#!/usr/bin/env python
"""
CICD Control
"""
#pylint: disable=invalid-name

from __future__ import print_function

import argparse
import atexit
import datetime
import glob
import inspect
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

import psutil
from openshift_tools.inventory_clients.inventory_util import Cluster
from openshift_tools.ansible.playbook_executor import PlaybookExecutor
from openshift_tools.utils.ssh_agent import SshAgent


OPERATIONS = []
AUTOKEYS_PATH = '/var/local/oo_autokeys'
AUTOKEYS_PREFIX = 'root_autokey'

def command(func):
    """ Store function data to be later registered as a command. """

    doc = func.__doc__
    doc = doc[1:doc.find('\n')]
    doc = doc[:1].lower() + doc[1:].rstrip('.')
    name = func.__name__.replace('_', '-')
    OPERATIONS.append((func, name, doc))

    return func

def parse_args():
    """ parse args """

    parser = argparse.ArgumentParser(description='Allow different operations to be performed on a cluster',
                                     epilog='Example: %(prog)s -c prod-cluster upgrade-control-plane')

    parser.add_argument('-c', '--cluster-id', required=True, help='the cluster to perform the operation on')
    parser.add_argument('-o', '--operation', required=True,
                        help='operation to perform: Some choices: {}'.format('\n'.join([i[1] for i in OPERATIONS])))

    # Various extra args
    parser.add_argument('--target-version', help='Openshift Target Version to use')
    parser.add_argument('--docker-version', help='Docker Version to use')
    parser.add_argument('--yum-repo-urls', help='List of comma seperated YUM URLS to add to the cluster')
    parser.add_argument('--scalegroup-ami', help='AMI to use for scaling up nodes with scalegroupis')
    parser.add_argument('--yum-openshift-ansible-url', help='Yum URL for openshift-ansible')

    parser.add_argument('--skip-statuspage', action='store_true', help='skip Status Page steps')
    parser.add_argument('--skip-zabbix', action='store_true', help='skip Zabbix Maintenance steps')
    parser.add_argument('--skip-config-loop', action='store_true', help='skip Config Loop steps')
    parser.add_argument('--test-cluster', action='store_true', help='Is this a test cluster')

    args = parser.parse_args()

    return args

def main():
    """ main function """

    args = parse_args()
    cicd_control = CICDControl(args.cluster_id, args.operation.replace('-', '_'), vars(args))
    cicd_control.main()

#pylint: disable=too-many-instance-attributes
class CICDControl(object):
    """  CICD Control """

    def __init__(self, cluster, operation, extra_args=None):
        """ init functions """

        self.cluster = Cluster(cluster)
        self.operation = operation

        # set up directory vars to help us out
        self.bin_dir = os.path.dirname(os.path.realpath(__file__))
        home_dir = os.path.realpath(os.path.join(os.environ['HOME']))
        aos_dir = os.path.realpath(os.path.join(os.environ['HOME'], 'aos-cd'))
        self.git_dir = os.path.realpath(os.path.join(aos_dir, 'git'))
        self.tmp_dir = os.path.realpath(os.path.join(aos_dir, 'tmp'))
        self.upgrade_log_path = os.path.realpath(os.path.join(home_dir, 'upgrade_logs', self.cluster.name))

        self.playbook_executor = PlaybookExecutor(self.bin_dir)

        self.extra_args = {}
        for k in extra_args:
            if extra_args[k] is not None:
                self.extra_args[k] = extra_args[k]

        print(self.extra_args)

    def main(self):
        """ main function of the class """

        # Kick off the keep alive thread
        keep_alive_thread = threading.Thread(target=CICDControl.keep_alive)
        keep_alive_thread.setDaemon(True)
        keep_alive_thread.start()

        atexit.register(self.atexit_cleanup)
        self.setup_log_dir()

        if self.operation.startswith('online-'):
            self.update_online_roles()

        valid_methods = [m[0] for m in inspect.getmembers(self) if inspect.ismethod(m[1])]
        if self.operation in valid_methods:
            operation_to_run = getattr(self, self.operation)
            operation_to_run()
        else:
            self.cluster_operation()

    def setup_log_dir(self):
        """ create the log dir """

        if not os.path.exists(self.upgrade_log_path):
            os.makedirs(self.upgrade_log_path, 0770)

    def cleanup_log_dir(self):
        """ cleanup the log dir """

        for cluster_file in glob.glob(os.path.join(self.upgrade_log_path, '*{}*'.format(self.cluster.name))):
            os.unlink(cluster_file)

    def atexit_cleanup(self):
        """ cleanup atexit """

        if 'openshift_ansible_dir' in self.extra_args:
            shutil.rmtree(self.extra_args['openshift_ansible_dir'])

        process = psutil.Process(os.getpid())
        for child in process.children():
            os.kill(child.pid, signal.SIGKILL)

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

    @staticmethod
    def keep_alive():
        """ This is a function to just run while """

        while True:
            now = datetime.datetime.now()
            #FIXME
            time.sleep(20)
            print(".... cicd-control still running: {} ....".format(now), file=sys.stderr)

    @command
    def update_ops_git_repos(self):
        """ update the ops git repos """

        print("\nUpdating the Ops Git Repos\n")

        self.playbook_executor('clone_ops_git_repos.yml')


    @command
    def update_online_roles(self):
        """ update the onnline roles with gogitit """

        print("\nUsing Online components from environment: {}\n".format(self.cluster.environment))

        subprocess.check_output(["/usr/bin/ssh-agent", "bash", "-c", "ssh-add "
                                 "{}/openshift-ansible-private/private_roles/aos-cicd/files/"
                                 "github_ops_bot_ssh_key.rsa; /usr/bin/gogitit sync -m "
                                 "./gogitit_online_{}.yml".format(self.git_dir, self.cluster.environment)])

    def get_latest_openshift_ansible(self):
        """ Download and extract the latest openshift-ansible """

        openshift_ansible_dir = tempfile.mkdtemp(prefix=os.path.join(self.tmp_dir, "openshift-ansible-"))

        pbe = PlaybookExecutor(os.path.join(self.git_dir, 'openshift-ansible-ops', 'playbooks', 'adhoc',
                                            'get_openshift_ansible_rpms'))

        pbe('extract_openshift_ansible_rpms.yml', {'cli_download_link' : self.extra_args['yum_openshift_ansible_url'],
                                                   'cli_download_dir' : openshift_ansible_dir})

        self.extra_args['openshift_ansible_dir'] = openshift_ansible_dir

        return openshift_ansible_dir


    @command
    def pre_check(self):
        """ Run a pre-upgrade check """

        self.cleanup_log_dir()

        # get the latest openshift-ansible rpms
        openshift_ansible_dir = self.get_latest_openshift_ansible()

        # Find the version of openshift-ansible
        osa_rpm_versions = subprocess.check_output(['rpm', '-qp', '--queryformat', '%{VERSION}-%{RELEASE}\n',
                                                    openshift_ansible_dir + '/rpms/*rpm'])
        osa_rpm_version = list(set(osa_rpm_versions.strip().split('\n')))[0]

        # Find the Openshift Version on the node

        with SshAgent() as agent:
            agent.add_autokey(AUTOKEYS_PATH, AUTOKEYS_PREFIX)

            _ = self.cluster.run_cmd_on_master("/usr/bin/yum clean all")
            _ = self.cluster.run_cmd_on_master("/usr/sbin/atomic-openshift-excluder unexclude")
            os_rpm_version = self.cluster.run_cmd_on_master("/usr/bin/repoquery --quiet --pkgnarrow=repos "
                                                            "--queryformat='%{version}-%{release}' "
                                                            "atomic-openshift")
            _ = self.cluster.run_cmd_on_master("/usr/sbin/atomic-openshift-excluder exclude")

            disk_usage = subprocess.check_output(["/usr/bin/opssh", "-c", self.cluster.name, "-t", "master", "-i",
                                                  "/usr/bin/df -h  / /var /var/lib/etcd | /usr/bin/uniq"])


        print("\nOpenshift Ansible RPM Version:   {}".format(osa_rpm_version))
        print("Openshift RPM Version:           {}\n".format(os_rpm_version))
        print("Filesystem usage for '/' and 'var':")
        print("================================================================")
        print(disk_usage)

    @command
    def storage_migration(self):
        """ storage migration operation """

        storage_migration_log = os.path.join(self.upgrade_log_path, "storage.migrate.log")
        print("\nRunning storage migration and logging to: {} on {}2\n".format(storage_migration_log,
                                                                               socket.gethostname()))

        storage_migration_cmd = ["/usr/local/bin/autokeys_loader", "ossh", "-l", "root",
                                 self.cluster.primary_master, "-c",
                                 "oc adm migrate storage --include='*' --confirm --loglevel=8"]

        with SshAgent() as agent:
            agent.add_autokey(AUTOKEYS_PATH, AUTOKEYS_PREFIX)

            # Run the command
            proc = CICDControl.run_cmd(storage_migration_cmd, storage_migration_log)

        if proc[0] == 0:
            os.unlink(storage_migration_log)
            print("\nStorage migration ran successfully; removed {}\n".format(storage_migration_log))
        else:
            print("\nStorage migration failed...")
            print("Printing last 100 lines of the log for convenience.")
            print("To see the full log, view '{}' on tower2.\n\n".format(storage_migration_log))

            with open(storage_migration_log, 'r') as log_file:
                log_file_contents = log_file.readlines()

            for line in log_file_contents[-min(len(log_file_contents), 100):]:
                print(line)

    @command
    def build_ci_msg(self):
        """  Streams the python script to the cluster master.
             Script outputs a json document.
        """

        ci_msg_cmd = ['ossh', '-l', 'root', self.cluster.primary_master, '-c',
                      "/usr/bin/python - {}".format(self.cluster.name)]

        build_ci_input = open(os.path.join(self.bin_dir, 'build-ci-msg.py'))

        with SshAgent() as agent:
            agent.add_autokey(AUTOKEYS_PATH, AUTOKEYS_PREFIX)

            proc = CICDControl.run_cmd(ci_msg_cmd, None, build_ci_input)

        for line in proc[1].split('\n'):
            if '=' in line:
                print(line)

    @command
    def status(self):
        """ do a cluster status """

        status_script = os.path.join(self.bin_dir, 'aos-cd-cluster-status.sh')

        with SshAgent() as agent:
            agent.add_autokey(AUTOKEYS_PATH, AUTOKEYS_PREFIX)
            proc = CICDControl.run_cmd([status_script, self.cluster.name])

        print(proc[1])

    @command
    def smoketest(self):
        """ do a smoketest on a cluster """

        smoketest_script = os.path.join(self.bin_dir, 'aos-cd-cluster-smoke-test.sh')

        with SshAgent() as agent:
            agent.add_autokey(AUTOKEYS_PATH, AUTOKEYS_PREFIX)
            proc = CICDControl.run_cmd([smoketest_script, self.cluster.name])

        print(proc[1])

    def cluster_operation(self):
        """ Call the cicd-operations.py script """

        openshift_ansible_operations = ['install', 'upgrade', 'upgrade_control_plane', 'upgrade_nodes',
                                        'upgrade_metrics', 'upgrade_logging']

        self.update_ops_git_repos()
        print(self.operation)
        if self.operation in openshift_ansible_operations:
            self.get_latest_openshift_ansible()

        # call the cicd operations
        #pylint: disable=relative-import
        # Moving this import here.  The hope is is that this will be updated via git before it's imported
        from ops_bin.cicd_operations import ClusterOperation
        operation = ClusterOperation(self.cluster.name, self.operation, self.extra_args)

        with SshAgent() as agent:
            agent.add_autokey(AUTOKEYS_PATH, AUTOKEYS_PREFIX)
            operation.main()

if __name__ == '__main__':
    main()

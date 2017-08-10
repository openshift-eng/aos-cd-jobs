# Collect logs from Online clusters

## Synopsis

````
  ssh -i online/logs_access_key opsmedic@use-tower2.ops.rhcloud.com \
      -- -u USER -c CLUSTER [-n node1 node2...] > logs.tar.gz
````

**NOTE**: the collected logs are dumped to the standard output as a compressed
tarball, so **you must redirect the output of ssh** to a file of your choice.

## SSH key to access logs

Access to logs is done via ssh to a bastion host as the *opsmedic* user with a
specific SSH key that is used for this purpose only. This SSH key is recreated
on a weekly basis and stored in the *rotating_keys* branch of the
[shared-secrets repo](https://github.com/openshift/shared-secrets/tree/rotating_keys).

## Information collected

The [log gathering script](../../tower-scripts/bin/gather-logs.sh) collects:

* Master info:

   - journal for these services: `atomic-openshift-master-{api,controllers}` and `etcd`
   - The output of `oc get node`
   - The output of the `/metrics` endpoint

* Selected nodes info:

   - journal for these services: docker, atomic-openshift-node, dnsmasq, openvswitch, ovs-vswitchd, ovsdb-server
   - The output of `oc describe node` for that node
   - The output of the `/metrics` endpoint for that node (via API proxy)

## Command usage

The log gathering command accepts 3 parameters:

- `-u username` (**mandatory**): specify your kerberos id here.

- `-c cluster` (**mandatory**): which cluster to collect logs from. Currently the list
     of accepted clusters is:

     - free-int
     - free-stg
     - starter-us-east-1
     - starter-us-east-2
     - starter-us-west-2

- `-n node1 node2...` (optional): an optional list of nodes to collect logs from

If you don't specify nodes with `-n`, only master-related information is
collected. If you need logs for the node-related services from the masters you
need to explicitly list them after `-n`.

**NOTE**: in order to separate ssh client parameters from the parameters of the
log collection script you must add `--` before the script's params.

Here's a summary of the workflow to get logs from a cluster:

 0. (one-time preparation) Clone the *shared-secrets* repo:

    ````
    $ git clone git@github.com:openshift/shared-secrets.git
    ````

 1. Check out the latest *rotating_keys* branch to get the current SSH
    key for log gathering and make sure it has acceptable perms for ssh:

    ````
    $ cd /path/to/your/cloned/shared-secrets
    $ git checkout rotating_keys
    $ git pull
    $ chmod 600 online/logs_access_key
    ````

 2. Collect logs from the cluster/nodes of choice. For example:

    ````
    $ ssh -i online/logs_access_key opsmedic@use-tower2.ops.rhcloud.com \
          -- -u YourKerberosID  -c free-stg                 \
             -n ip-172-31-65-74.us-east-2.compute.internal  \
                ip-172-31-69-53.us-east-2.compute.internal  \
          > logs.tar.gz
    ````

### Contents of the generated tarball

A sample generated log archive looks like this:

````
$ tree logs-free-stg-201708101636/
logs-free-stg-201708101636/
├── gather-logs.debug
├── masters
│   ├── journal
│   │   ├── atomic-openshift-master-api
│   │   │   ├── 52.14.191.156
│   │   │   ├── 52.14.8.110
│   │   │   └── 52.15.177.230
│   │   ├── atomic-openshift-master-controllers
│   │   │   ├── 52.14.191.156
│   │   │   ├── 52.14.8.110
│   │   │   └── 52.15.177.230
│   │   └── etcd
│   │       ├── 52.14.191.156
│   │       ├── 52.14.8.110
│   │       └── 52.15.177.230
│   └── reports
│       ├── metrics.txt
│       └── nodes.txt
└── nodes
    ├── ip-172-31-65-74.us-east-2.compute.internal
    │   ├── describe.txt
    │   ├── journal
    │   │   ├── atomic-openshift-node
    │   │   ├── dnsmasq
    │   │   ├── docker
    │   │   ├── openvswitch
    │   │   ├── ovsdb-server
    │   │   └── ovs-vswitchd
    │   └── metrics.txt
    └── ip-172-31-69-53.us-east-2.compute.internal
        ├── describe.txt
        ├── journal
        │   ├── atomic-openshift-node
        │   ├── dnsmasq
        │   ├── docker
        │   ├── openvswitch
        │   ├── ovsdb-server
        │   └── ovs-vswitchd
        └── metrics.txt

11 directories, 28 files
````

# Collect logs from Online clusters

## Synopsis

````
  online/gather-logs.sh -u USER -c CLUSTER [-n node1 node2...] > logs.tar.gz
````

**NOTE**: the collected logs are dumped to the standard output as a compressed
tarball, so **you should redirect the output** to a file of your choice.

## SSH key to access logs

Access to logs is done via ssh to a bastion host with a specific SSH key that is
used for this purpose only. This SSH key is recreated on a weekly basis and
stored in the *rotating_keys* branch of the
[shared-secrets repo](https://github.com/openshift/shared-secrets/tree/rotating_keys).

## Command usage

The log gathering command accepts 3 parameters:

- `-u username` (**required**): specify your kerberos id here.

- `-c cluster` (**required**): which cluster to collect logs from. If you
  provide an invalid cluster id you will get a list of the cluster names that
  are currently accepted by the script.

- `-n node1 node2...` (optional): an optional list of nodes to collect logs from

If you don't specify nodes with `-n`, only master-related information is
collected. If you need logs for the node-related services from the masters you
need to explicitly list them after `-n`.

Here's a summary of the workflow to get logs from a cluster:

 0. (one-time preparation) Clone the *shared-secrets* repo:

    ````
    $ git clone git@github.com:openshift/shared-secrets.git
    ````

 1. Check out the latest *rotating_keys* branch to get the current SSH
    key for log gathering:

    ````
    $ cd /path/to/your/cloned/shared-secrets
    $ git checkout rotating_keys
    $ git pull
    ````

 2. Collect logs from the cluster/nodes of choice. For example:

    ````
    $ online/gather-logs.sh -u YourKerberosID  -c free-stg  \
             -n ip-172-31-65-74.us-east-2.compute.internal  \
                ip-172-31-69-53.us-east-2.compute.internal  \
          > logs.tar.gz
    ````

### Direct ssh invocation

The `gather-logs.sh` helper script in the `shared-secrets` repo just makes sure that the key is available with correct permissions, that output is properly redirected, and then invokes ssh.

If you want you can use ssh directly, taking care of argument separation. This is an example invocation via direct ssh, equivalent to the example above:

    ````
    $ ssh -i online/logs_access_key opsmedic@use-tower2.ops.rhcloud.com \
          -- -u YourKerberosID  -c free-stg                 \
             -n ip-172-31-65-74.us-east-2.compute.internal  \
                ip-172-31-69-53.us-east-2.compute.internal  \
          > logs.tar.gz
    ````

**NOTE**: in order to separate ssh client parameters from the parameters of the
log collection script you must add `--` before the script's params.

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

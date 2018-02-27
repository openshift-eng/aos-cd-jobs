# `sjb` YAML Syntax Reference

A job configuration using `sjb` will take one of three forms: a stand-alone job,
one that inherits from another or one that triggers other jobs. A standalone
job can declare options; a job with a parent can extend or override any option
from the parent.

Parent-child relationships can nest -- to generate a job, the topmost parent
configuration is loaded, then iteratively extended and overridden by children
configurations until the bottommost configuration has been evaluated.

## `description`

`description` is an optional string field that will override the default job
description. The syntax is:

```yaml
description: ""
```

## `children`

`children` is a list which, if present, will configure the job to have child
jobs in a multi-job build. If this field is present, the only other acceptable
configuration fields are `timer`, `email`, and `merge` or `test`. The syntax
is:

```yaml
children: [] # a list of job names (YAML filenames without extension under sjb/config/test_cases)
```

## `parent`

`parent` is an optional string field that takes already existing
job configuration and includes it into the current job configuration.
The syntax is:

```yaml
parent: "" # path to a job configuration with respect to sjb/config directory
```

It is used together with `extensions` and `overrides` keyword that specifies
a list of configuration options (see example at the bottom).

A configuration option can _either_ be found in `extensions:` _or_ in
`overrides` but not in both.

## `extensions`

`extensions` is a dictionary used together with `parent` field that extends
a dictionary of parent's configuration options.
The syntax is:

```yaml
parent: ""
extensions: {} # a dictionary of configuration options
```

## `overrides`

`overrides` is a dictionary used together with `parent` field that replaces
a dictionary of parent's configuration options.
The syntax is:

```yaml
parent: ""
overrides: {} # a dictionary of configuration options
```

## `timer`

`timer` is an optional field that holds a `cron` entry and will configure the
job to trigger on this timer. Normal Jenkins `cron` syntax is expected. The
syntax is:

```yaml
timer: "" # cron entry, e.g. 'H H * * *'
```

## `email`

`email` is an optional list of e-mail addresses for who to contact when the job
fails. The syntax is:

```yaml
email: [] # list of e-mail addresses
```

## `junit_analysis`

`junit_analysis` is an optional flag to enable or disable the "Publish
JUnit test result report" post-build step. It defaults to `True`

```yaml
junit_analysis: False # JUnit analysis is disabled
```

## `merge` and `test`

`merge` and `test` are optional fields that mark the job as one that uses the
`test-pull-requests` utility for signalling that a test succeeded or merging
a pull request given a test success. If `test-pull-requests` is configured to
run a job for a `[test]` tag, the `test` field should be present in the job
configuration. Likewise with `[merge]` and the `merge` field. The syntax is:

```yaml
merge: "" # repo name under github.com/openshift
```

```yaml
test: "" # repo name under github.com/openshift
```

Note: one of `merge` or `test` can be specified, but not both.

## `parameters`

`parameters` is an optional field which adds parameters to the Jenkins job. The
field contains a list of parameter definitions. The parameter definition syntax
is:

```yaml
parameters:
  - name: ""          # environment variable name
    description: ""   # human-readable description
    default_value: "" # default value [optional]
```

## `provision`

`provision` is a required field which gives the options for provisioning a VM
in AWS EC2 for the job. The syntax is:

```yaml
provision:
  os: ""       # operating system. only 'rhel' is supported
  stage: ""    # image stage. one of ['bare', 'base', 'build', 'install', 'fork']
  provider: "" # cloud provider. only 'aws' is supported
```

## `sync_repos`

`sync_repos` is an optional field which declares which repositories are to be
synced and how they are to be synced. This field will add build stages to sync
the repository as well as update the job description with details about what
repos the job instance is being run with. The syntax is:

```yaml
sync_repos:
  - name: "" # repository name under github.com/openshift
    type: "" # 'pull_request' for a PR sync [optional]
```

## `sync`

`sync` is an optional field which declares which repositories are to be synced
and how they are to be synced. This field will add build stages to sync the
repository as well as update the job description with details about what repos
the job instance is being run with. This stage makes use of Prow pod utilities
for syncing and reporting sync results and therefore requires that the job is
triggered by Prow. Either this option or `sync_repos` can be provided, but not
both. The syntax is:

```yaml
sync:
  - pullspec # format org,repo=branch:branch-sha,[pull-number:pull-sha,...]
```

## `actions`

`actions` is an optional list of actions to take in the job. Each action will
declare a type and can optionally declare a timeout. The syntax is:

```yaml
actions:
  - type: ""   # one of ['forward_parameters', 'host_script', 'script']
    timeout: 0 # in seconds [optional]
```

### `type: "forward_parameters"`

the `forward_parameters` action will make an environment variable available on
the Jenkins master in the `$WORKSPACE` also available to scripts running on the
remote host in EC2. The syntax is:

```yaml
actions:
  - type: "forward_parameters"
    timeout: 0 # in seconds [optional]
    parameters: [] # a list of environment variables
```

### `type: "host_script"`

the `host_script` action will run a set of shell commands on the Jenkins master
in the job's `$WORKSPACE`. The syntax is:

```yaml
actions:
  - type: "host_script"
    timeout: 0 # in seconds [optional]
    title: ""  # a human-readable title for the step
    script: "" # inline shell script to run, no character escaping necessary
```

### `type: "script"`

the `script` action will run a set of shell commands in the specified directory
on the remote VM in EC2. The syntax is:

```yaml
actions:
  - type: "script"
    timeout: 0 # in seconds [optional]
    title: ""      # a human-readable title for the step
    repository: "" # the repository under github.com/openshift to `cd` into [optional]
    script: ""     # inline shell script to run, no character escaping necessary
```

## `post_actions`

`post_actions` is an optional list of actions to be taken after the main job
actions have finished or errored. The syntax is identical to that for [`actions`](#actions):

```yaml
post_actions:
  - type: "" # one of ['forward_parameters', 'host_script', 'script']
```

## `artifacts`

`artifacts` is an optional list of files or directories on the remote VM which
will be retrieved into the `$WORKSPACE` on the Jenkins master after the job is
finished. The syntax is:

```yaml
artifacts: [] # a list of absolute paths
```

## `generated_artifacts`

`generated_artifacts` is an optional mapping of shell commands to artifact file
names. For each mapping entry, the command will be run on the remote VM and the
output captured to the filename in the `$WORKSPACE` on the Jenkins master. The
syntax is:

```yaml
generated_artifacts:
  filename: "shell command" # note: this is a map, not a list
```

## `system_journals`

`system_journals` is an optional list of `systemd` units for which the system
journal should be gathered from the remote VM. Each unit name will be used to
expand: `journalctl --unit {{ unit }} --no-pager --all --lines=all`. The syntax
is:

```yaml
system_journals: [] # a list of unit names (e.g. 'docker')
```

## Standalone Example: `common/test_cases/origin.yml`

This job definition serves as a proto-job, used as a parent for all other
Origin test jobs. It lives in [`config/common`](./config/common/test_cases/origin.yml).

```yaml
parameters: []
provision:
  os: "rhel"
  stage: "base"
  provider: "aws"
sync_repos:
  - name: "origin"
actions:
  - type: "script"
    title: "use a ramdisk for etcd"
    timeout: 300
    script: |-
      sudo su root <<SUDO
      mkdir -p /tmp
      mount -t tmpfs -o size=4096m tmpfs /tmp
      mkdir -p /tmp/etcd
      chmod a+rwx /tmp/etcd
      restorecon -R /tmp
      echo "ETCD_DATA_DIR=/tmp/etcd" >> /etc/environment
      SUDO
post_actions: []
artifacts:
  - "/data/src/github.com/openshift/origin/_output/scripts"
generated_artifacts:
  installed_packages.log: 'sudo yum list installed'
  avc_denials.log: 'sudo ausearch -m AVC -m SELINUX_ERR -m USER_AVC'
  docker.info: 'sudo docker version && sudo docker info && sudo docker images && sudo docker ps -a'
  filesystem.info: 'sudo df -h && sudo vgs && sudo lvs'
  pid1.journal: 'sudo journalctl _PID=1 --no-pager --all --lines=all'
system_journals:
  - docker.service

```

## Inheritance Example: `test_cases/test_branch_origin_check.yml`

This job definition defines the job that runs unit tests and verification for
Origin. It inherits from the above `origin.yml` job and lives in [`config`](./config/test_cases/test_branch_origin_check.yml).

```yaml
parent: 'common/test_cases/origin.yml'
extensions:
  actions:
    - type: "script"
      title: "verify commit history"
      repository: "origin"
      timeout: 7200
      script: |-
        # run commitchecker outside release container as it needs
        # access to git; also explicitly force godeps verification
        branch="$( git rev-parse --abbrev-ref --symbolic-full-name HEAD )"
        if [[ "${branch}" == "master" ]]; then
          RESTORE_AND_VERIFY_GODEPS=1 make verify-commits -j
        fi
    - type: "script"
      title: "run check and verify tasks"
      repository: "origin"
      script: |-
        OS_BUILD_ENV_PRESERVE=_output/scripts hack/env TEST_KUBE='true' JUNIT_REPORT='true' make check -j -k
```

Note: a configuration option can _either_ be found in `extensions:` _or_ in
`overrides` but not in both.

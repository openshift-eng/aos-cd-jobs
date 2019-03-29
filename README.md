# aos-cd-jobs

This repository backs Jenkins jobs on a couple of Jenkins masters.

## Jenkins pipeline definitions under `scheduled-jobs/`

Scheduled pipeline definitions are stored in this directory so they are not
indexed by the process described below and turned into a branch on the
multi-branch pipeline.  This is done to facilitate enabling and disabling the
jobs without needing to change the source code on the repository, and any job
that requires that should be under this directory.

|     Job Name     | Description |
| ---------------- | ----------- |
| `build/ose`      | Runs build/ose daily. Presently used to build 3.6 for daily integration test environments. |
| `build/t-th`     | Runs build/ose every Tuesday and Thursday for particular builds of OCP. |

## Jenkins pipeline definitions under `jobs/`

An internal [Continuous Infrastructure Jenkins instance](https://buildvm.openshift.eng.bos.redhat.com:8443/) indexes
Jenkinsfiles in the branches of this repository.  The branches are automatically generated from the Jenkinsfiles that live under
the `jobs/` directory on the `master` branch. The job responsible for generating, updating and removing the branches can be found
in the [`Jenkinsfile`](Jenkinsfile) at the root directory. The branch update job is configured to be executed periodically, but
can be manually triggered in [jenkins](https://buildvm.openshift.eng.bos.redhat.com:8443/job/update-branches/).

The scripts used by the job described above are [`pruner.py`](aos_cd_jobs/pruner.py), which removes branches for jobs that no
longer exist, and [`updater.py`](aos_cd_jobs/updater.py), which creates/updates branches for existing jobs. A "job" is any
directory under the `jobs/` directory which contains a `Jenkinsfile`.  Every branch is an orphan (doesn't contain any history) and
its contents are the contents of the `master` branch with the corresponding directory under `jobs/` copied to the root directory
and the `jobs/` directory removed.

As an example, the contents of the root and `jobs/build/openshift-scripts` directories in master are currently:

    ├── build-scripts
    │   └── …
    ├── Jenkinsfile
    ├── jobs
    │   …
    │   └── build
    │       └── openshift-scripts
    │           ├── Jenkinsfile
    │           ├── README.md
    │           └── scripts
    │               └── merge-and-build-openshift-scripts.sh
    …
    └── README.md

The final contents of the `build/openshift-scripts` branch, after the execution of the job, will be:

    ├── build-scripts
    │   └── …
    ├── Jenkinsfile
    ├── README.md
    …
    └── scripts
        └── merge-and-build-openshift-scripts.sh

Note that the files `Jenkinsfile` and `README.md` in the master branch exist both in the root directory and in the job directory.
Because of the sequence of steps described above, the former will be overwritten by the latter.

Jobs under the `jobs/build/` directory are indexed at the
[`aos-cd-builds`](https://buildvm.openshift.eng.bos.redhat.com:8443/job/aos-cd-builds/) grouping. Some jobs are described below. 

|          Job Name          | Description |
| -------------------------- | ----------- |
| `build/ocp`                | Main build task for OCP 3.7. Also builds openshift-ansible 3.7 and all OCP images. |
| `build/ose`                | Main build task for OCP <=3.6. Also builds openshift-ansible artifiacts and jenkins images. |
| `build/make-puddle`        | Create an Atomic OpenShift puddle on `rcm-guest`. |
| `build/openshift-scripts`  | Builds RPMs and container images for the [OpenShift Online](https://github.com/openshift/online) team. |
| `build/refresh-images`     |             |
| `build/scan-images`        | Scans the images for CVEs using openscap. |
| `sprint/stage-to-prod`     | Promote RPMs from the staging repositories to the production repositories (Copies files from [latest/ in the enterprise online-stg](https://mirror.openshift.com/enterprise/online-stg/latest/) repo to [online-prod/lastest](https://mirror.openshift.com/enterprise/online-prod/latest/). Also copies files from [libra rhel-7-libra-stage](https://mirror.ops.rhcloud.com/libra/rhel-7-libra-stage/) to [libra's latest online-prod](https://mirror.ops.rhcloud.com/libra/online-prod/latest/) in a new directory based on the day's date.). |
| `sprint/control`           | Send out messages about dev/stage cut to engineering teams. |
| `package-dockertested`     | Tests new Brew builds of Docker and tags them into a [mirror repo](https://mirror.openshift.com/enterprise/rhel/dockerextra/x86_64/os/Packages/) for use by the CI systems. |
| `starter/operation`        | Run specific operations on starter clusters. |
| `starter/upgrade`          | Runs an openshift-ansible based upgrade on a starter cluster. |

## Jenkins Job Builder configuration under `jjb/`

Jenkins Job Builder definitions under the `jjb/` directory are not currently used to underpin any jobs, but were an investigation
into how the JJB system was used by the AOS CI team to build and support CI jobs for the `openshift-ansible` repository.

## Continuous Upgrade job configuration under `continuous-upgrade/`

Continuous Upgrade job is using Jenkins Job Builder framework to continuously upgrade an Openshift cluster.

To be able to generate XML configuration of continuous-upgrade jobs you need to install [jenkins-jobs tool](https://docs.openstack.org/infra/jenkins-job-builder/installation.html). After installing the tool run [`continuous-upgrade/generate-jobs.py`](continuous-upgrade/generate-jobs.py) to re-generate XMLs of the jobs. 

To push the changes in any of the jobs to the server use:
```shell
sjb/push-update.sh continuous-upgrade/generated/continuous-upgrade_JOB_NAME.xml
```

## Custom XML Generator configuration under `sjb/`

A custom XML generator lives under the `sjb/` directory. This generator is meant to be a tightly scoped tool that would help us
bridge the gap between monolithic scripts inside of Freestyle Jenkins Jobs and segmented Jenkins Pipelines driven by source-
controlled Groovy scripts and libraries.

The generator understands a small set of `action`s, each of which is underpinned by a Python module under
[`sjb/actions/`](sjb/actions). A configuration YAML file is read in by [`sjb/generate.py`](sjb/generate.py) and used to generate a
set of input variables to the [Jinja job template XML](sjb/templates/test_case.xml). Jobs can depend on a parent to reuse
configuration. Documentation on the YAML syntax can be found at [`syntax.md`](./sjb/syntax.md).

A typical workflow for a developer making changes to the job would look like:

 - make edits to a configuration file under `sjb/config/`
 - run `sjb/generate.sh`
 - commit changes
 - run `sjb/push-update-automatic.sh` once changes are approved and merged into `master`

Your local environment needs Python dependencies installed to run `sjb/generate.sh` - this can be done via the command `$ pip install -r sjb/requirements.txt`.
You will also need [pip](https://pypi.org/project/pip/), which comes bundled with most Python distributions.

In order to test a job, it is necessary to copy a configuration file under `sjb/config` to a new YAML file with a different name,
then re-generate XML and use the following command to push only your test job up to the server:
```shell
sjb/push-update.sh sjb/generated/YOUR_TEST_JOB.xml
````
Cleanup of these jobs post-test is still manual.

If changes are being made to the files under `sjb/` in this repository, it is not enough to copy a job configuration and run it to
test the changes. Instead, it will be necessary to mark the copied job as syncing a pull request for `aos-cd-jobs` using the `type`
field on the repository as per [the spec](./sjb/syntax.md#sync_repos). Then, when running your copied job, configure it at run-time
to merge in your pull request by entering in your pull request number in the appropriate parameter field in the Jenkins UI when
starting the job.

### Push Credentials

Note: the `sjb/push-update{,-automatic}.sh` scripts expect `$USERNAME` and `$PASSWORD` to be set as envars when they are run.
`$USERNAME` is your user with which you log in to the Jenkins master at [ci.openshift](http://ci.openshift.redhat.com/).
`$PASSWORD` is a Jenkins API token you have to generate through the Jenkins UI. As a logged-in user, click your username in the upper right hand of the UI. After the account page loads, click "Configure" on the right hand side, and after the configuration page loads, you will see an option to generate a new token. Copy this to your password store, since it is only displayed for copy/pasting when you first generate it.
The `$USERNAME` and `$PASSWORD` are used for basic auth against the server on push actions.

## Pull Request approvers under `approvers/`

In order to ensure that pull requests are only merged during phases of a sprint where they are appropriate, all `[merge]` jobs now
call out to an approver on the Jenkins master that will determine if the pull request should merge into the specific branch and
repo that it targets.

When running `[merge]` on a PR, developers will optionally be able to add `[severity: value]` extensions, where value can take:

 - none ( `[merge]` )
 - bug ( `[merge][severity: bug]` )
 - blocker ( `[merge][severity: blocker]` )
 - low-risk ( `[merge][severity: lowrisk]` )

The `lowrisk` severity is special in that all approvers other than the [`closed_approver.sh`](approvers/closed_approver.sh), will
allow merges with it. Developers should use this tag when they are making changes to code in the repository that does not make up
any part of the shipped product and therefore does not have any chance of impacting deployments.

There will be four possible designations for any branch in your repo:

<table>
  <tr>
    <th colspan="2" rowspan="2"></th>
    <th colspan="4">Pull Request Severity<br></th>
  </tr>
  <tr>
    <td>None</td>
    <td>Bug</td>
    <td>Blocker</td>
    <td>Low-Risk</td>
  </tr>
  <tr>
    <td rowspan="4">Branch Stage<br></td>
    <td>Open</td>
    <td>✔️</td>
    <td>✔️</td>
    <td>✔️</td>
    <td>✔️</td>
  </tr>
  <tr>
    <td>DevCut</td>
    <td>❌</td>
    <td>✔️</td>
    <td>✔️</td>
    <td>✔️</td>
  </tr>
  <tr>
    <td>StageCut</td>
    <td>❌</td>
    <td>❌</td>
    <td>✔️</td>
    <td>✔️</td>
  </tr>
  <tr>
    <td>Closed</td>
    <td>❌</td>
    <td>❌</td>
    <td>❌</td>
    <td>❌</td>
  </tr>
</table>

### Consulting an Approver

In order to determine if a pull request should merge, consult the [`approve.sh`](approvers/approve.sh) script on the Jenkins
master on which the job runs:

```shell
approve.sh "${REPO}" "${TARGET_BRANCH}" "${MERGE_SEVERITY:-"none"}"
```

### Configuring Branch Status

To configure a branch status, run the [`configure_approver`](https://ci.dev.openshift.redhat.com/jenkins/job/configure_approver/)
job on the [ci.dev](https://ci.dev.openshift.redhat.com/jenkins/) Jenkins master. This job will configure the approver you ask
for as well as propagate the changes to the [ci.openshift](http://ci.openshift.redhat.com/) server. The job runs the
[`configure_approver`](approvers/configure_approver.sh) script:

```shell
for repo in ${REPOSITORIES}; do
    for branch in ${BRANCHES}; do
        configure_approver.sh "${repo}" "${branch}" "${STAGE}"
    done
done

list_approvers.sh
```

### Approver Design

Approvers are configured by creating a symbolic link at `~jenkins/approvers/openshift/${REPO}/${TARGET_BRANCH}/approver` for the
approver that is requested for that branch. The approvers are the [`closed_approver.sh`](approvers/closed_approver.sh),
[`open_approver.sh`](approvers/open_approver.sh), [`devcut_approver.sh`](approvers/devcut_approver.sh), and
[`stagecut_approver.sh`](approvers/stagecut_approver.sh) scripts in this repository under [`approvers/`](approvers/).

### Developer Workflow

Development on approver scripts in this repository is fairly straightforward. When your changes are ready and have been merged,
run the [`push.sh`](approvers/push.sh) script to deploy your changes to the Jenkins masters. You will need to have your SSH config
set up for the `ci.openshift` and `ci.dev.openshift` hosts in order for this script to work.

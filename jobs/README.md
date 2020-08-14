# Jenkins pipeline definitions under `jobs/`

NOTE: The [jenkins server](https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/aos-cd-builds/)
is internal and locked down so only ART team members can access it.

Jobs under the `jobs/build/` directory are indexed in a multibranch pipeline in the
[`aos-cd-builds`](https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/aos-cd-builds/) folder.

https://mojo.redhat.com/docs/DOC-1206910 explains how to access, develop, and use these.

## Deployment

[Jenkins](https://saml.buildvm.openshift.eng.bos.redhat.com:8888/)
indexes Jenkinsfiles in the branches of this repository.  The branches are
automatically generated from the Jenkinsfiles that live under the `jobs/`
directory on the `master` branch. The job responsible for generating, updating
and removing the branches can be found in the [`Jenkinsfile`](Jenkinsfile) at
the root directory. The branch update job is configured to be executed
when the master branch gets a new commit, but can be manually triggered in
[jenkins](https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/update-branches/job/master/).

The scripts used by the job described above are [`pruner.py`](aos_cd_jobs/pruner.py), which removes branches for jobs that no
longer exist, and [`updater.py`](aos_cd_jobs/updater.py), which creates/updates branches for existing jobs. A "job" is any
directory under the `jobs/` directory which contains a `Jenkinsfile`.  Every branch is an orphan (doesn't contain any history) and
its contents are the contents of the `master` branch with the corresponding directory under `jobs/` copied to the root directory
and the `jobs/` directory removed.

As an example, the contents of the root and `jobs/build/advisories` directories in master are currently:

    …
    ├── Jenkinsfile
    ├── jobs
    │   …
    │   └── build
    │       └── advisories
    │           ├── Jenkinsfile
    │           ├── README.md
    │           └── advisories.groovy
    ├── pipeline-scripts
    │   └── …
    …
    └── README.md

The final contents of the `build/advisories` branch, after the execution of the job, will be:

    …
    ├── advisories.groovy
    ├── Jenkinsfile  (from advisories dir)
    ├── pipeline-scripts
    │   └── …
    …
    └── README.md    (from advisories dir)

Note that the files `Jenkinsfile` and `README.md` in the master branch exist both in the root directory and in the job directory.
Because of the sequence of steps described above, the former will be overwritten by the latter.

## Developer Workflow

See [How do I hack on the jobs?](https://mojo.redhat.com/docs/DOC-1206910#jive_content_id_How_do_I_hack_on_the_jobs).

## Common conventions

It is a very good idea to get familiar with [commonlib.groovy](https://github.com/openshift/aos-cd-jobs/blob/master/pipeline-scripts/commonlib.groovy).

### Standard parameters

#### DRY\_RUN

A common parameter, used when testing (but not standardized anywhere).

When set, the job should make no changes, just echo what the job would have done.
Preferably this should exercise as much job logic as possible without changing production data.

#### MOCK

When set, the job runs just far enough to define job properties, and then exits
with an error. This should be used whenever job properties change before trying
to use the updated properties.

Jenkinsfiles generally put in code the job properties (importantly, job
parameters) that Jenkins uses to define the policy and UI for the job.
Jenkins does not run this code until the job is actually executed, so before
running the first time, the job has no parameters, and when the code changes,
changes to the job properties are only reflected after the job has run again.

The MOCK parameter allows the job to run once to pick up new job properties
without executing any of the logic that is the purpose of the job, to avoid the
case where running it with the wrong properties (e.g. no parameters or old
parameter names) would be undesirable.

Standardized in [`commonlib.mockParam()`](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L155)

Jobs that use this need to invoke [`commonlib.checkMock()`](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L145)
after defining job properties but before beginning their logic. When invoked,
this throws an error if there is no MOCK parameter defined (on the first run)
or if it is true (to pick up changes).

#### SUPPRESS\_EMAIL

Standard parameter to prevent email being sent during testing, but still create
email texts and archive them in the job run.  It defaults to sending email when
deployed under [aos-cd-builds](https://saml.buildvm.openshift.eng.bos.redhat.com:8888/job/aos-cd-builds/)
and defaults to suppressing it anywhere else.

Standardized in [`commonlib.suppressEmailParam()`](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L173)

[`commonlib.email()`](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L245)
automatically respects this parameter so jobs do not need to branch their logic.

#### VERSION or BUILD\_VERSION or MINOR\_VERSION

This refers to the OCP minor version like 3.11 or 4.5; available choices are given in a pulldown.
There must be a matching branch `openshift-VERSION` in the [ocp-build-data repository](https://github.com/openshift/ocp-build-data/branches).
Jobs with this parameter cannot be run against arbitrary branches in ocp-build-data.

Standardized in [`commonlib.ocpVersionParam()`](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L164)

### List parameters

Jenkins doesn't provide a good way to enter multiple values in a parameter. We typically need this to specify images or packages to build.

* Because doozer and elliott accept comma-separater parameters like this, most
  jobs with parameters like this accept a comma-separated list.
* Because nobody likes fooling around with syntax, most of them use
  [parseList()](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L245)
  or
  [cleanCommaList()](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L202)
  from `commonlib` to split a list by any combination of commas and whitespace.
* Usually (but not in all cases!) these lists refer to distgit names defined in ocp-build-data.

So it usually doesn't matter if you enter "foo,bar" or "foo bar" or "foo , bar" or cut/paste newlines or tabs.

### User input, retries, and slack notifications

Sometimes a job needs to have a human look at something or provide something
before continuing. In this case the job can pause and change its status to
indicate that input is needed.

A common pattern is that something exceptional happens and the job needs a human to tell it how/whether to proceed.
This has been abstracted out in [commonlib](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L508-L578).

Since we humans would rather not have to pay attention to our job runs all day,
this integrates slack to notify humans when a job is waiting on input.
Typically a job should send these to one of our version-specific channels. The
`release` job uses this heavily, for example to [let release-artists know
release tests failed](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/jobs/build/release/Jenkinsfile#L341-L345).

### Concurrency and locks

Job stages will sometimes show "paused for X seconds" or similar. They are waiting on a lock.

For most jobs, disabling concurrency entirely (only running one instance at a
time) is not granular enough, nor does it prevent conflicting jobs (perhaps a
hack job for the same thing) from running.

Use the [`lock` step](https://www.jenkins.io/doc/pipeline/steps/lockable-resources/#lock-lock-shared-resource)
to scope locking only to the conflict that needs to be avoided.  For example in
the [ocp4 job](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/jobs/build/ocp4/Jenkinsfile#L110)
there are locks to prevent conflicting dist-git commits or RPM composes for the
same version (but different versions can run concurrently just fine).

If a job needs to check whether a lock is free without actually locking, see
[`commonlib.canLock()`](https://github.com/openshift/aos-cd-jobs/blob/fbdf70d1e82e375d013978d5a4583008fafcf45e/pipeline-scripts/commonlib.groovy#L476).

## Job documentation template

Jobs should (WIP) each have a README to explain what they are for and how to use them.
They should also have a [description](https://github.com/openshift/aos-cd-jobs/blob/908864ae4b444c7fb382836564b4fb9fb21d3dce/pipeline-scripts/commonlib.groovy#L135)
and link to their docs.

The following is a template to start out a new README.md. Copy and remove two hash marks from each title.

### (Brief description of job goes here)

#### Purpose

What is it for? Why do we need it?

#### Timing

When would this run or under what conditions should a human run it?

#### Parameters

##### Standard parameters DRY\_RUN, MINOR\_VERSION, MOCK, SUPPRESS\_EMAIL (if relevant)

See [Standard Parameters](/jobs/README.md#standard-parameters).

##### Parameter ...

List each parameter, examples of what should/not go in it, effects it has, gotchas to avoid, etc.

#### Known issues

##### Issue ...

What is known not to work? If it sometimes breaks, what should the ARTist do about it?

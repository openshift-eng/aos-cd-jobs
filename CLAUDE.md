# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains Jenkins pipeline jobs and automation scripts for building and releasing OpenShift Container Platform (OCP). The primary purpose is to back Jenkins jobs on internal CI/CD masters used by Red Hat's Automated Release Team (ART).

## Repository Architecture

### Branch Management System

The repository uses a unique branching model where the `master` branch contains job definitions under `jobs/`, and these are automatically transformed into individual branches for Jenkins indexing:

- **Root Jenkinsfile**: Defines the `update-branches` job that runs periodically
- **updater.py**: Creates/updates branches for jobs (any directory under `jobs/` with a Jenkinsfile)
- **pruner.py**: Removes branches for jobs that no longer exist
- Each job branch is an orphan branch containing the master branch content with the specific job directory promoted to root

**Example**: `jobs/build/ocp4/Jenkinsfile` becomes the `build/ocp4` branch with its contents at the root.

### Directory Structure

- **jobs/**: Main pipeline job definitions (indexed automatically into branches)
  - `jobs/build/`: Build-related jobs (ocp3, ocp4, microshift, etc.)
  - `jobs/signing/`: Artifact signing jobs
  - `jobs/scanning/`: Image health scanning jobs
  - `jobs/maintenance/`: Maintenance and cleanup jobs

- **scheduled-jobs/**: Jobs with specific schedules not indexed by the branch system

- **pipeline-scripts/**: Reusable Groovy libraries
  - `commonlib.groovy`: Core utilities (shell wrapper, email, version parsing, S3 sync)
  - `buildlib.groovy`: Build-specific utilities (doozer, elliott, spec file handling)
  - `slacklib.groovy`: Slack notification utilities
  - `release.groovy`: Release management functions
  - `deploylib.groovy`: Deployment utilities

- **vars/**: Jenkins shared library global variables
  - `artToolRelease.groovy`: ART tools release functions
  - `pollGitRefs.groovy`: Git reference polling

- **aos_cd_jobs/**: Python modules for branch management
  - `updater.py`, `pruner.py`, `common.py`

- **approvers/**: Pull request merge approval system for sprint phases
  - Bash scripts that enforce merge policies based on severity and sprint stage

- **config/**: Configuration files (artcd.toml for artcd tool)

- **tekton-pipelines/**: Tekton pipeline definitions and scripts

- **build-scripts/**: Build-related scripts (golang RPMs, rosa-sync)

- **hacks/**: Utility scripts and one-off tools

## Key Technologies

- **Jenkins Pipelines**: Groovy-based declarative and scripted pipelines
- **Python 3.11**: For automation tools (installed via `uv` package manager)
- **Doozer**: ART's tool for building OCP images and RPMs
- **Elliott**: ART's tool for managing Errata advisories
- **artcd**: Automation tool for OCP release workflows
- **Brew**: Red Hat's build system (rpm/container builds)
- **AWS S3**: For artifact storage and mirroring

## Common Development Tasks

### Running Tests

Python tests use the standard unittest framework:
```bash
python -m unittest aos_cd_jobs/updater_test.py
python -m unittest aos_cd_jobs/pruner_test.py
```

For pipeline-scripts Groovy tests:
```bash
# Tests are in *_test.groovy files like buildlib_test.groovy, commonlib_test.groovy
# These are typically run within Jenkins pipeline test jobs
```

### Working with Pipeline Scripts

When loading shared libraries in a Jenkinsfile:
```groovy
node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib  // commonlib is loaded by buildlib
    def slacklib = commonlib.slacklib   // slacklib is loaded by commonlib

    // Use the libraries
    buildlib.doozer("--version")
    commonlib.shell(script: "echo 'Hello'")
}
```

### Standard Job Parameters

Most jobs use these common parameters (defined in commonlib.groovy):

- **MOCK**: Pick up job parameter changes without running job logic
- **DRY_RUN**: Run without side effects (no production changes)
- **ASSEMBLY**: Assembly name to build (default: "stream" for latest content)
- **BUILD_VERSION** / **MINOR_VERSION**: OCP version (e.g., "4.15", "4.16")
- **DOOZER_DATA_PATH**: Fork of ocp-build-data repo (default: openshift-eng/ocp-build-data)
- **DOOZER_DATA_GITREF**: Git ref for ocp-build-data (default: openshift-X.Y branch)
- **SUPPRESS_EMAIL**: Prevent actual email sending during testing
- **ART_TOOLS_COMMIT**: Override art-tools version (format: `ghuser@commitish`)

### Using Doozer and Elliott

Both tools are wrapper functions in buildlib.groovy:

```groovy
// Doozer automatically uses ASSEMBLY parameter
buildlib.doozer("--group=openshift-4.15 images:list")

// Elliott for errata management
buildlib.elliott("--group=openshift-4.15 --assembly=stream find-builds --kind=rpm")

// Both support capture option
def output = buildlib.doozer("config:read-group --yaml arches", [capture: true])
```

### Shell Command Execution

Use `commonlib.shell()` instead of raw `sh` for better error handling and archival:

```groovy
// Basic usage
commonlib.shell(script: "brew list-tagged ocp-4.15-candidate")

// Capture output
def result = commonlib.shell(script: "git rev-parse HEAD", returnStdout: true)

// Return all output streams
def results = commonlib.shell(script: "some-command", returnAll: true)
// results.stdout, results.stderr, results.combined, results.returnStatus

// Always archive artifacts even on success
commonlib.shell(script: "make test", alwaysArchive: true)
```

### Python Virtual Environment Setup

Jobs automatically set up a Python virtual environment with ART tools:

```groovy
buildlib.initialize()  // Sets up venv, installs doozer, elliott, pyartcd
// Tools are then available in PATH
```

The venv is created at `${WORKSPACE}/art-venv` using Python 3.11 with `uv` package manager.

### Version Management

OCP versions are centrally defined in commonlib.groovy:

```groovy
ocp4Versions = ["4.21", "4.20", "4.19", "4.18", "4.17", "4.16", "4.15", "4.14", "4.13", "4.12"]
ocp3Versions = ["3.11"]

// Get supported architectures for a version
def arches = buildlib.branch_arches("openshift-4.15")  // Returns ["x86_64", "aarch64", "s390x", "ppc64le"]

// Architecture name translation
def brewArch = commonlib.brewArchForGoArch("amd64")  // Returns "x86_64"
def goArch = commonlib.goArchForBrewArch("x86_64")   // Returns "amd64"
```

### Locking and Concurrency

Use Jenkins `lock` step to prevent conflicts:

```groovy
lock("ocp-4.15-build") {
    // Only one build per version at a time
    buildlib.doozer("images:build")
}
```

Check lock availability without blocking:
```groovy
if (commonlib.canLock("ocp-4.15-build", timeout_seconds=10)) {
    // Lock is available
}
```

## Important Architectural Concepts

### Job Deployment Flow

1. Developer modifies a job definition in `jobs/some-category/job-name/Jenkinsfile`
2. Changes are committed and pushed to `master` branch
3. The `update-branches` job runs (periodically or on push)
4. `updater.py` creates/updates the `some-category/job-name` branch
5. Jenkins multibranch pipeline indexes the branch and updates the job

### Approver System

The approver system controls when PRs can be merged based on sprint phase:

- **Open**: All merges allowed
- **DevCut**: Only bug/blocker/low-risk merges
- **StageCut**: Only blocker/low-risk merges
- **Closed**: Only low-risk merges

Usage in merge jobs:
```bash
approve.sh "${REPO}" "${TARGET_BRANCH}" "${MERGE_SEVERITY:-none}"
```

### Record Log Parsing

Doozer creates a `record.log` file with structured build information:

```groovy
def record_log = buildlib.parse_record_log("artcd_working/doozer_working/")
def builds = record_log.get('build', [])
def failed_builds = buildlib.get_failed_builds(record_log)
```

### S3 Artifact Syncing

For syncing repos to mirror.openshift.com:

```groovy
// Sync RPM repository
commonlib.syncRepoToS3Mirror(
    "./local_repo_dir",
    "/pub/openshift-v4/x86_64/dependencies/rpms/4.15-el9",
    remove_old: true,
    issue_cloudfront_invalidation: true
)

// Sync arbitrary directory
commonlib.syncDirToS3Mirror(
    "./artifacts",
    "/pub/openshift-v4/x86_64/clients/ocp/4.15.0",
    delete_old: true
)
```

### Error Handling and Retries

Use retry wrappers for user intervention:

```groovy
commonlib.retrySkipAbort("build images", slackOutput) {
    buildlib.doozer("images:build")
}
// On failure, prompts user to Retry, Skip, or Abort
```

## Testing and Development

### Testing Job Changes Locally

1. Fork the repository
2. Modify your fork's job definition
3. Run the job with `DOOZER_DATA_PATH` pointing to your fork
4. Use `MOCK=true` first to validate parameter changes
5. Use `DRY_RUN=true` to test logic without side effects

### Common Pitfalls

- **Always call `commonlib.checkMock()`** after defining job properties but before main logic
- **Use `commonlib.shell()` not raw `sh`** for proper error handling and archival
- **Load libraries in correct order**: buildlib → commonlib → slacklib
- **Architecture naming**: Be aware of brew vs go arch naming differences
- **S3 paths**: Validate paths don't use virtual/read-only locations with `commonlib.checkS3Path()`
- **List parameters**: Use `commonlib.parseList()` or `commonlib.cleanCommaList()` to handle user input flexibly

## Key Files to Reference

- `pipeline-scripts/commonlib.groovy` - Most commonly used utilities
- `pipeline-scripts/buildlib.groovy` - Build and tool wrappers
- `jobs/build/ocp4/Jenkinsfile` - Primary OCP4 build job (reference implementation)
- `jobs/README.md` - Detailed job conventions and parameter documentation
- `config/artcd.toml` - artcd tool configuration (email, Jira, advisory settings)

## Environment and Credentials

Jobs run on `openshift-build-1` or similar nodes with these key credentials:

- `openshift-bot`: SSH key for GitHub access
- `art-dash-db-login`: Database credentials for doozer/elliott
- `aws-credentials-file`: AWS credentials for S3 operations
- `jenkins-service-account`: Kubernetes service account
- `gitlab-ocp-release-schedule-schedule`: GitLab token
- `jboss-jira-token`: Jira API token
- Various Slack tokens and webhook URLs

## Architecture-Specific Builds

OCP supports multiple architectures with arch-specific naming:

- **Brew arches**: `x86_64`, `aarch64`, `s390x`, `ppc64le`, `multi`
- **Go arches**: `amd64`, `arm64`, `s390x`, `ppc64le`, `multi`
- Release controllers use Go arch names in URLs: `https://amd64.ocp.releases.ci.openshift.org`
- Use helper functions for translation between naming schemes

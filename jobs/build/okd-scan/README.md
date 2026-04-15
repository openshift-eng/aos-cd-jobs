# OKD Scan Jenkins Job

## Overview

This Jenkins job scans OKD image sources for changes and triggers OKD builds when relevant changes are detected.

## Job Location

- **Path**: `aos-cd-builds/build/okd-scan`
- **Jenkinsfile**: `aos-cd-jobs/jobs/build/okd-scan/Jenkinsfile`

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `VERSION` | choice | - | OKD version to scan (e.g., 4.21, 4.22) |
| `ASSEMBLY` | string | stream | Assembly to be scanned |
| `DOOZER_DATA_PATH` | string | https://github.com/openshift-eng/ocp-build-data | ocp-build-data fork to use |
| `DOOZER_DATA_GITREF` | string | (empty) | Optional git branch/tag/sha to use |
| `IMAGE_LIST` | string | (empty) | Optional comma/space-separated list of images to scan |
| `DRY_RUN` | boolean | false | Run scan without triggering subsequent jobs |

## What It Does

1. **Checks if version is enabled** - Exits early if version not in `OKD_ENABLED_VERSIONS`
2. **Initializes environment** with proper credentials and workspace
3. **Scans OKD images** using `artcd okd-scan` with `--variant=okd`
   - The `--variant=okd` flag tells doozer to skip checks not relevant for OKD:
     - ARCHES_CHANGE (OKD doesn't rebuild for arch changes)
     - NETWORK_MODE_CHANGE (OKD always uses open network)
     - PACKAGE_CHANGE (OKD doesn't rebuild for RPM changes)
   - Only valid OKD rebuild reasons are reported:
     - NO_LATEST_BUILD
     - LAST_BUILD_FAILED
     - NEW_UPSTREAM_COMMIT
     - UPSTREAM_COMMIT_MISMATCH
     - ANCESTOR_CHANGING
     - CONFIG_CHANGE
     - BUILDER_CHANGING
     - DEPENDENCY_NEWER
4. **Triggers OKD build** if changes are detected (all reported changes are valid)
5. **Archives logs** for debugging

## Example Usage

### Manual Trigger (Dry Run)
```
VERSION: 4.21
ASSEMBLY: stream
DRY_RUN: true
```

### Manual Trigger (Production)
```
VERSION: 4.21
ASSEMBLY: stream
DRY_RUN: false
```

### Scan Specific Images Only
```
VERSION: 4.21
ASSEMBLY: stream
IMAGE_LIST: openshift-apiserver,openshift-controller-manager
DRY_RUN: false
```

## Scheduled Execution

Cron schedule: `0 0,12 * * *` (at 00:00 and 12:00 daily)

## Required Credentials

The job requires the following Jenkins credentials:
- `jenkins-service-account` - Jenkins service account username
- `jenkins-service-account-token` - Jenkins service account token
- `redis-server-password` - Redis password for lock management
- `openshift-bot-token` - GitHub token for repository access
- `art-bot-slack-token` - Slack bot token for notifications
- `quay-auth-file` - Konflux image registry auth
- `konflux-gcp-app-creds-prod` - GCP credentials for Konflux
- `creds_registry.redhat.io` - Red Hat registry credentials
- `openshift-bot` (SSH key) - For git operations

## Locking

The job uses two locks to prevent conflicts:
- `SCAN_OKD` - Prevents multiple scan jobs for the same version
- `BUILD_OKD` - Prevents scanning while a build is in progress

If either lock is held, the job will skip execution.

## Code Location

Pipeline implementation:
- `pyartcd/pyartcd/pipelines/okd_scan.py`
- `pyartcd/pyartcd/pipelines/scheduled/schedule_okd_scan.py`

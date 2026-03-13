# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository (`aos-cd-jobs`) manages Jenkins-based CI/CD infrastructure for OpenShift Container Platform (OCP) builds and releases. It's maintained by the ART (Automated Release Tooling) team at Red Hat.

**Key Concept**: Jobs are defined in the `jobs/` directory, and an automated process converts each job directory into a separate orphan branch that Jenkins indexes. The root `/Jenkinsfile` orchestrates this branch creation/update process.

## Architecture

### Branch Management System

The core architecture uses **automatic branch generation**:

1. **Master branch** contains all source code and job definitions under `jobs/`
2. **Job branches** are automatically created as orphan branches (no history)
   - Each directory in `jobs/` with a `Jenkinsfile` → one branch
   - Example: `jobs/build/ocp4/Jenkinsfile` → creates branch `build/ocp4`
   - Branch contents = master files + job-specific files (with `jobs/` directory removed)
3. **Update process** runs via `/Jenkinsfile`:
   ```bash
   python -m aos_cd_jobs.pruner    # Remove branches for deleted jobs
   python -m aos_cd_jobs.updater   # Create/update branches for existing jobs
   ```

### Directory Structure

```
├── jobs/                          # Primary Jenkins job definitions (62 jobs)
│   ├── build/                     # 54 build-related jobs (ocp4, gen-assembly, etc.)
│   ├── maintenance/               # Maintenance operations
│   ├── scanning/                  # Security scanning
│   └── signing/                   # Artifact signing
├── scheduled-jobs/                # Periodic job triggers (29 jobs)
├── pipeline-scripts/              # Groovy shared libraries (2,960 LOC total)
│   ├── buildlib.groovy           # Build operations and tool initialization
│   ├── commonlib.groovy          # Common utilities, version management
│   ├── release.groovy            # Complex release pipeline logic
│   ├── slacklib.groovy           # Slack notifications
│   └── deploylib.groovy          # Deployment utilities
├── src/com/redhat/art/           # Groovy utility classes
│   ├── Version.groovy            # Semantic versioning
│   ├── Rpm.groovy                # RPM package operations
│   └── GitHubRepository.groovy   # Git operations
├── aos_cd_jobs/                  # Python branch management utilities
│   ├── updater.py                # Creates/updates job branches
│   └── pruner.py                 # Removes stale branches
├── approvers/                    # PR approval system scripts
├── tekton-pipelines/             # Kubernetes/Tekton pipelines
├── hacks/                        # Utility scripts and tools
└── vars/                         # Jenkins pipeline global variables
```

### Key Python Modules

- **`aos_cd_jobs/updater.py`**: Creates orphan branches from job definitions. Core function: `update_branches()`
- **`aos_cd_jobs/pruner.py`**: Removes branches for non-existent jobs. Core function: `prune_remote_refs()`
- **`aos_cd_jobs/common.py`**: Shared utilities and repository initialization

### Groovy Shared Libraries

The `pipeline-scripts/` directory contains the foundation for all Jenkins jobs:

**`commonlib.groovy`** (713 LOC):
- Version constants: `ocp3Versions`, `ocp4Versions`, `ocp5Versions`
- Architecture translation: `goArchForBrewArch()` (converts between Go and Brew arch naming)
- Standard parameters: `ocpVersionParam()`, `artToolsParam()`, `dryrunParam()`, `mockParam()`
- Utilities: `describeJob()`, `email()`, `shell()`

**`buildlib.groovy`** (750 LOC):
- `initialize()`: Sets up Python venv, GOPATH, Kerberos auth
- `doozer()`: Execute doozer commands
- `elliott()`: Execute elliott commands
- `kinit()`: Kerberos authentication for distgit access

**`release.groovy`** (916 LOC):
- Complex release operations
- `stageGenPayload()`: Generate release payloads
- `destReleaseTag()`: Calculate release tags

**Groovy Classes** (`src/com/redhat/art/`):
- `Version.groovy`: Semantic version operations, comparison, version bumping
- `Rpm.groovy`: RPM package operations (tag, build, release)
- `RpmSpec.groovy`: RPM spec file parsing
- `GitHubRepository.groovy`: Git tag and branch operations

## Common Development Tasks

### Running Tests

Python tests use `unittest` + `mock`:
```bash
# Run Python unit tests
python -m unittest aos_cd_jobs.pruner_test
python -m unittest aos_cd_jobs.updater_test

# Or run all tests
python -m unittest discover aos_cd_jobs
```

Groovy tests exist but are typically run within Jenkins environment:
- `pipeline-scripts/buildlib_test.groovy`
- `pipeline-scripts/commonlib_test.groovy`
- `src/com/redhat/art/VersionTest.groovy`

### Setting Up Development Environment

**Using VSCode Dev Container**:
1. Install Remote Development Extension Pack
2. Open project in VSCode
3. F1 → "Remote-Containers: Reopen in Container"
4. ⚠️ Must be on Red Hat VPN for dependency resolution

**Manual Setup**:
```bash
# Create Python virtual environment
python3 -m venv env/
source env/bin/activate

# Install dependencies
pip install gitpython

# For dev container builds with podman
podman build --build-arg USERNAME=$USER --build-arg USER_UID=$(id -u) \
             -f .devcontainer/dev.Dockerfile -t local/aos-cd-jobs
```

### Branch Update Process

The `/Jenkinsfile` at the root runs on Jenkins node `openshift-build-1` and executes:
```bash
python3 -m venv ../env/
. ../env/bin/activate
pip install gitpython
python -m aos_cd_jobs.pruner    # Only runs on official repo
python -m aos_cd_jobs.updater
```

This process is triggered automatically on master commits or can be run manually via the `update-branches` Jenkins job.

## Jenkins Job Patterns

### Standard Job Structure

```groovy
node {
    timestamps {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("job-name", """<description>""")

        properties([
            disableResume(),
            buildDiscarder(logRotator(artifactDaysToKeepStr: '60', daysToKeepStr: '60')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.artToolsParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                    // Job-specific parameters
                ]
            ]
        ])

        stage("stage-name") {
            // Implementation
        }
    }
}
```

### Common Parameters

All jobs should support these standard parameters:
- **`ASSEMBLY`**: Assembly name (default: "stream" for development builds)
- **`BUILD_VERSION`**: OCP version (4.12, 4.13, 4.23, 5.0, etc.)
- **`DOOZER_DATA_PATH`**: Override for ocp-build-data repository fork
- **`DRYRUN`**: Execute without side effects (boolean)
- **`MOCK`**: Skip actual operations for testing (boolean)

### Tool Integration Pattern

```groovy
def buildlib = load("pipeline-scripts/buildlib.groovy")
buildlib.initialize(false)  // Setup venv, GOPATH, kinit

// Execute doozer commands
buildlib.doozer("images:build --version ${params.BUILD_VERSION}")

// Execute elliott commands
buildlib.elliott("advisory:create --version ${params.BUILD_VERSION}")
```

### Credential Management

```groovy
withCredentials([
    file(credentialsId: 'art-publish.app.ci.kubeconfig', variable: 'KUBECONFIG'),
    string(credentialsId: 'exd-ocp-buildvm-bot-prod.user', variable: 'BOT_USER'),
]) {
    // Operations requiring credentials
}
```

## Important Tools

External tools used throughout the jobs:
- **doozer**: Metadata and build management (ocp-build-data-mgt)
- **elliott**: Advisory/errata management (errata-tool-ansible)
- **oc**: OpenShift CLI for app.ci cluster operations
- **brew**: Brew/Koji build system for RPMs
- **tito**: RPM release automation

## Multi-Architecture Support

The codebase extensively handles multiple architectures:

**Architecture names** (Brew vs Go):
```groovy
// Use commonlib.goArchForBrewArch(arch) to convert
brewArches = ["x86_64", "s390x", "ppc64le", "aarch64", "multi"]
goArches   = ["amd64",  "s390x", "ppc64le", "arm64",   "multi"]
```

## Pull Request Approval System

Located in `approvers/` directory. Controls when PRs can merge based on sprint phase:

```bash
# Check if PR can merge
approvers/approve.sh REPO BRANCH SEVERITY

# Severities: none, bug, blocker, low-risk
# Branch stages: open, devcut, stagecut, closed
```

**Approval Matrix**:
- **open**: All severities allowed
- **devcut**: Requires bug/blocker/low-risk (blocks "none")
- **stagecut**: Requires blocker/low-risk only
- **closed**: All blocked (except low-risk for non-product code)

Configure via Jenkins job: `configure_approver`

## Version Management

Supported OCP versions (see `commonlib.groovy`):
- **OCP 3.x**: 3.11
- **OCP 4.x**: 4.12 through 4.23
- **OCP 5.x**: 5.0

Version constants are centralized in `commonlib.groovy` for consistency across all jobs.

## Key Job Categories

**Build Jobs** (`jobs/build/`):
- `ocp4`, `ocp3`, `okd4`: Main version builds
- `gen-assembly`: Generate release assembly definitions
- `promote-assembly`: Publish official releases to mirrors
- `build-sync*`: Sync builds to multiple downstream systems
- `tag-rpms`, `publish-rpms`: RPM lifecycle management
- `rhcos_sync`: RHCOS (Red Hat CoreOS) image synchronization

**Scheduled Jobs** (`scheduled-jobs/`):
- Trigger builds on a schedule
- Use simplified pattern: `build(job: '../aos-cd-builds/build%2Fname', ...)`

## Code Style Conventions

### Python
- Use type hints for all function parameters and return values
- Triple-quoted docstrings with format:
  ```python
  def function_name(param: str) -> dict:
      """
      Brief description.

      Arg(s):
          param (str): Description.
      Return Value(s):
          dict: Description.
      """
  ```
- Prefix private functions with underscore: `_private_function()`
- Shebang: `#!/usr/bin/env python3`
- Testing: Use `unittest` framework with `mock` library

### Groovy
- Load shared libraries: `def buildlib = load("pipeline-scripts/buildlib.groovy")`
- Always use `commonlib.describeJob()` to set job description
- Use `timestamps {}` wrapper for all pipeline code
- Prefer `commonlib.shell()` over direct `sh` for better error handling

## Important Notes

- **Red Hat VPN Required**: Many operations require active VPN connection
- **Jenkins Nodes**: Jobs run on `openshift-build-1` or similar nodes
- **SSH Keys**: Branch updates use SSH authentication (`openshift-bot` key)
- **Kerberos**: Required for distgit operations (handled by `buildlib.kinit()`)
- **Job Branches**: Never manually edit job branches - they're auto-generated from master
- **Testing Changes**: To test changes to `aos_cd_jobs/` or `pipeline-scripts/`, create a PR and configure test job to merge that PR at runtime

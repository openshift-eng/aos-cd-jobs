#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("sweep", """
        ---------------------------------------
        Sweep bugs into the standard advisories
        ---------------------------------------
        Timing: This runs after component builds (ocp3/ocp4/custom jobs).
        Can be run manually but this should be rarely needed.

        Bugs are attached into the appropriate advisories for the release,
        according to those recorded in ocp-build-data group.yml.
        For 3.11, all bugs are swept into the rpm advisory.
        For 4.y, bugs are swept into the image or extras advisory.
        CVEs are not currently swept by this job at all.

        Any bugs in the MODIFIED state are attached, without regard for whether
        their PRs have actually merged or been built. This causes them to
        transition to the ON_QA state.
        Bugs which are already attached and in the MODIFIED state are also
        transitioned to ON_QA so QE will look at them.

        Optionally, builds from our brew candidate tags may also be swept. This
        will only work with advisories in the NEW_FILES state (bugs can be
        attached to advisories in the QE state as well, but not builds).
    """)


    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '90'
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    commonlib.mockParam(),
                    booleanParam(
                        name: 'SWEEP_BUILDS',
                        defaultValue: true,
                        description: 'Sweep and attach builds to advisories',
                    ),
                ],
            ],
        ]
    )

    commonlib.checkMock()

    def version = params.BUILD_VERSION
    doozerOpts = "--group openshift-${version}"
    stage("Init") {
        echo "Initializing bug sweep for ${version}. Sync: #${currentBuild.number}"
        currentBuild.displayName = "${version} bug sweep"

        buildlib.elliott "--version"
        sh "which elliott"

        buildlib.kinit()
    }

    // short circuit to UNSTABLE (not FAILURE) when automation is frozen
    if (!buildlib.isBuildPermitted(doozerOpts)) {
        currentBuild.result = 'UNSTABLE'
        currentBuild.description = 'Builds not permitted'
        echo('This build is being terminated because it is not permitted according to current group.yml')
        return
    }

    currentBuild.description = "Repairing state and sweeping new bugs.\n"
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(version)
    def kinds = major >= 4 ? ["image", "extras"] : ["rpm"]

    stage("Repair bug state") {
        currentBuild.description += "* Moving attached bugs in MODIFIED state to ON_QA...\n"
        for (kind in kinds) {
            retry (3) {
                try {
                    buildlib.elliott "--group=openshift-${version} repair-bugs --use-default-advisory ${kind} --auto"
                } catch (elliottErr) {
                    echo("Error repairing (will retry a few times):\n${elliottErr}")
                    sleep(time: 1, unit: 'MINUTES')
                    throw elliottErr
                }
            }
        }
    }

    stage("Sweep bugs") {
        currentBuild.description += "* Searching for and attaching new bugs in MODIFIED state...\n"
        retry (3) {
            try {
                buildlib.elliott "--group=openshift-${version} find-bugs --mode sweep --into-default-advisories"
            } catch (elliottErr) {
                echo("Error sweeping bugs (will retry a few times):\n${elliottErr}")
                sleep(time: 1, unit: 'MINUTES')
                throw elliottErr
            }
        }
    }

    stage("Sweep builds") {
        if (!params.SWEEP_BUILDS) {
            currentBuild.description += "* Not sweeping builds\n"
            return
        }
        if (params.DRY_RUN) {
            echo("Skipping attach builds to advisory for dry run")
            return
        }
        buildlib.attachBuildsToAdvisory(["rpm", "image"], params.BUILD_VERSION)
    }
    currentBuild.description = "Ran without errors\n---------------\n" + currentBuild.description
}

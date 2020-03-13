#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    properties(
        [
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
    def major = version[0]
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
    def kind = (major == '4') ? 'image' : 'rpm'

    stage("Repair bug state") {
        try {
            currentBuild.description += "* Moving attached bugs in MODIFIED state to ON_QA...\n"
            buildlib.elliott "--group=openshift-${version} repair-bugs --use-default-advisory ${kind} --auto" 
        } catch (elliottErr) {
            currentBuild.description = "Error repairing:\n${elliottErr}"
            throw elliottErr
        }
    }

    stage("Sweep bugs") {
        try {
            currentBuild.description += "* Searching for and attaching new bugs in MODIFIED state...\n"
            buildlib.elliott "--group=openshift-${version} find-bugs --mode sweep --use-default-advisory ${kind}"
        } catch (elliottErr) {
            currentBuild.description += "Error sweeping bugs:\n${elliottErr}"
            throw elliottErr
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

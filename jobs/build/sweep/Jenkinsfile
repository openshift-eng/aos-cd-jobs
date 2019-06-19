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
                ],
            ],
        ]
    )

    commonlib.checkMock()

    def version = params.BUILD_VERSION
    def major = version[0]
    stage("Init") {
        echo "Initializing bug sweep for ${version}. Sync: #${currentBuild.number}"
        currentBuild.displayName = "${version} bug sweep"

        buildlib.elliott "--version"
        sh "which elliott"

        buildlib.kinit()
    }

    try {
        stage("Sweep bugs") {
            currentBuild.description = "Searching for and attaching bugs"
            buildlib.elliott "--group=openshift-${version} find-bugs --mode sweep --use-default-advisory ${major == '4' ? 'image' : 'rpm'}"
            currentBuild.description = "Ran bug attaching command without errors"
        }
    } catch (findBugsError) {
        currentBuild.description = "Error sweeping:\n${findBugsError}"
        throw findBugsError
    }
}

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
                ]
            ]
        ]
    )


    stage("Init") {
	echo "Initializing bug sweep for ${params.BUILD_VERSION}. Sync: #${currentBuild.number}"
	currentBuild.displayName = "${params.BUILD_VERSION} bug sweep"

        buildlib.elliott "--version"
        sh "which elliott"

	buildlib.kinit()
    }

    try {
	stage("Repair bugs") {
	    currentBuild.description = "Searching for and repairing bugs in invalid states"
	    buildlib.elliott "--group=openshift-${params.BUILD_VERSION} repair-bugs --auto --use-default-advisory rpm"
	    currentBuild.description = "Ran bug repair command without errors"
	}

	stage("Sweep bugs") {
	    currentBuild.description = "Searching for and attaching bugs"
	    buildlib.elliott "--group=openshift-${params.BUILD_VERSION} find-bugs --auto --use-default-advisory rpm"
	    currentBuild.description = "Ran bug repair and attaching commands without errors"
	}
    } catch (findBugsError) {
	currentBuild.description = "Error repair/sweeping:\n${findBugsError}"
	throw findBugsError
    }
}

#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def commonlib = release.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '500')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'RELEASE_NAME',
                        description: 'The name of the release to add to Cincinnati via PRs',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'ADVISORY_NUM',
                        description: 'Internal advisory number for release (i.e. https://errata.devel.redhat.com/advisory/??????)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'GITHUB_ORG',
                        description: 'The github org containing cincinnati-graph-data fork to open PRs against (use for testing)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "openshift"
                    ],
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()
    release.openCincinnatiPRs(params.RELEASE_NAME.trim(), params.ADVISORY_NUM.trim(), params.GITHUB_ORG.trim())
    buildlib.cleanWorkdir("${env.WORKSPACE}")
}

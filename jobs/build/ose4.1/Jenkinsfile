#!/usr/bin/env groovy

node {
    checkout scm
    def commonlib = load("pipeline-scripts/commonlib.groovy")
    properties([
        buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '')),
        disableConcurrentBuilds(),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    name: 'DRY_RUN',
                    description: 'Take no action, just echo what the build would have done.',
                    $class: 'BooleanParameterDefinition',
                    defaultValue: false
                ],
                [
                    name: 'NEW_VERSION',
                    description: '(Optional) version for build instead of most recent\nor "+" to bump most recent version',
                    $class: 'StringParameterDefinition',
                    defaultValue: ""
                ],
                [
                    name: 'FORCE_BUILD',
                    description: 'Build regardless of whether source has changed',
                    $class: 'BooleanParameterDefinition',
                    defaultValue: false
                ],
                commonlib.mockParam(),
            ]
        ]
    ])

    commonlib.checkMock()
    currentBuild.displayName = "ocp: [${params.NEW_VERSION ?: '4.1'}]"

    b = build job: 'build%2Focp4', propagate: false,
        parameters: [
            string(name: 'BUILD_VERSION', value: '4.1'),
            string(name: 'NEW_VERSION', value: params.NEW_VERSION),
            booleanParam(name: 'FORCE_BUILD', value: params.FORCE_BUILD),
            booleanParam(name: 'DRY_RUN', value: params.DRY_RUN),
        ]

    currentBuild.displayName = "ocp:${b.displayName}"
    currentBuild.result = b.result
}

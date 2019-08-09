#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'RELEASE',
                        description: 'Release Version on mirror.openshift.com to set to latest (e.g. 4.1.0)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'OC_MIRROR_DIR',
                        description: 'artifacts path of https://mirror.openshift.com (i.e. ocp, ocp-dev-preview)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "ocp"
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-team-art@redhat.com'
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()



    try {
        sshagent(['aos-cd-test']) {
            stage("sync ocp clients") {
                sh "./set-latest.sh ${env.WORKSPACE} ${RELEASE} ${OC_MIRROR_DIR}"
            }
        }
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-cicd@redhat.com",
            subject: "Error setting latest ocp client",
            body: "Encountered an error while setting latest ocp client: ${err}");
        currentBuild.description = "Error while setting latest ocp client:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
    buildlib.cleanWorkdir("${env.WORKSPACE}")
}

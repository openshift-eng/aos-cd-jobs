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
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-odo-sync@redhat.com',
                            'moahmed@redhat.com'
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    try {
        sshagent(['aos-cd-test']) {
            stage("sync odo") {
                withCredentials([string(credentialsId: 'GITHUB_TOKEN', variable: 'accessToken')]) {
                    buildlib.invoke_on_rcm_guest("publish-odo-binary.sh ${accessToken}")
                }
            }
        }
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error syncing odo client",
            body: "Encountered an error while syncing odo client: ${err}");
        currentBuild.description = "Error while syncing odo client:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}

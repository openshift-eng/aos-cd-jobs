#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("kn_sync", """
        ----------------------------------------------
        Sync the knative (serverkess) client to mirror
        ----------------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/clients/serverless/

        Timing: This is only ever run by humans, upon request.
    """)


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
                    string(
                        name: 'KN_VERSION',
                        description: 'the version of OpenShift Serverless CLI binaries',
                        defaultValue: "0.2.3"
                    ),
                    string(
                        name: 'KN_URL',
                        description: 'the RPM download url of OpenShift Serverless CLI binaries',
                        defaultValue: ""
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'nshaikh@redhat.com',
                            'aos-art-automation+failed-kn-client-sync@redhat.com',
                        ].join(',')
                    ),
                    commonlib.suppressEmailParam(),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )
    commonlib.checkMock()

    try {
        sshagent(['aos-cd-test']) {
            stage("sync kn") {
                buildlib.invoke_on_rcm_guest("publish-kn-binary.sh", params.KN_VERSION, params.KN_URL)
            }
        }
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation+failed-kn-client-sync@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error syncing kn client",
            body: "Encountered an error while syncing kn client: ${err}");
        currentBuild.description = "Error while syncing kn client:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}

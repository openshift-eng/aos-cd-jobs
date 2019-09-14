#!/usr/bin/env groovy

node {
    checkout scm
    def prerelease = load("pipeline-scripts/release.groovy")
    def buildlib = prerelease.buildlib
    def commonlib = prerelease.commonlib
    def quay_url = "quay.io/openshift-release-dev/ocp-release-nightly"

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
                        name: 'FROM_RELEASE_TAG',
                        description: 'Build tag to pull from (i.e. 4.1.0-0.nightly-2019-04-22-005054), pre-release job the release name is same as FROM_RELEASE_TAG',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'DRY_RUN',
                        description: 'Only do dry run test and exit.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'MIRROR',
                        description: 'Sync clients to mirror.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: true
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-release@redhat.com'
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                    commonlib.suppressEmailParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()

    buildlib.cleanWorkdir("${env.WORKSPACE}")

    try {
        sshagent(['aos-cd-test']) {
            release_info = ""
            from_release_tag = "${params.FROM_RELEASE_TAG}"
            name = from_release_tag.split("nightly")[0]+"nightly"
            // must be able to access remote registry for verification
            buildlib.registry_quay_dev_login()

            currentBuild.displayName = "#${currentBuild.number} - ${from_release_tag}"
            if (params.DRY_RUN) { currentBuild.displayName += " [dry run]"}
            if (!params.MIRROR) { currentBuild.displayName += " [no mirror]"}

            stage("versions") { prerelease.stageVersions() }

            stage("validation") { prerelease.stageValidation(quay_url, from_release_tag, -1) }

            stage("payload") { prerelease.stageGenPayload(quay_url, from_release_tag, from_release_tag, "", "", "") }

            if (params.MIRROR) {
                stage("client sync") { prerelease.stageClientSync(name, 'ocp-dev-preview') }
                stage("set client latest") { prerelease.stageSetClientLatest(from_release_tag, 'ocp-dev-preview') }
            }
        }
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Error running OCP Pre-Release",
            body: "Encountered an error while running OCP pre release: ${err}");
        currentBuild.description = "Error while running OCP pre release:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}

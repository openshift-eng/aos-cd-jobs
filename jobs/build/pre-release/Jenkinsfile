#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
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
                        description: 'Release tag on api.ci (e.g. 4.1.0-0.nightly-2019-04-22-005054)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'NAME_OVERRIDE',
                        description: 'Release name (if not specified, uses FROM_RELEASE_TAG)',
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
                        name: 'SET_CLIENT_LATEST',
                        description: 'Set latest links for client.',
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

            currentBuild.displayName = "#${currentBuild.number} - ${params.FROM_RELEASE_TAG}"
            if (params.DRY_RUN) { currentBuild.displayName += " [dry run]"}
            if (!params.MIRROR) { currentBuild.displayName += " [no mirror]"}

            arch = release.getReleaseTagArch(params.FROM_RELEASE_TAG)

            def dest_release_tag = params.FROM_RELEASE_TAG
            if ( params.NAME_OVERRIDE.trim() != "" ) {
                dest_release_tag = params.NAME_OVERRIDE
            }

            stage("versions") { release.stageVersions() }

            buildlib.registry_quay_dev_login()

            def CLIENT_TYPE = "ocp-dev-preview"

            stage("validation") {
                release.stageValidation(quay_url, dest_release_tag, -1)
            }

            stage("build payload") {
                release.stageGenPayload(quay_url, dest_release_tag, params.FROM_RELEASE_TAG, "", "", "")
            }

            stage("mirror tools") {
                if ( params.MIRROR ) {
                    release.stagePublishClient(quay_url, dest_release_tag, arch, CLIENT_TYPE)
                }
            }

            stage("set client latest") {
                if ( params.MIRROR && params.SET_CLIENT_LATEST ) {
                    release.stageSetClientLatest(dest_release_tag, arch, CLIENT_TYPE)
                }
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

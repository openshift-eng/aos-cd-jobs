#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '25')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'FROM_RELEASE_TAG',
                        description: 'Build tag to pull from (i.e. 4.1.0-0.nightly-2019-04-22-005054)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'NAME',
                        description: 'Release name (i.e. 4.1.0-rc0)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'DESCRIPTION',
                        description: 'Release description for metadata',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'ADVISORY',
                        description: 'Optional: Image release advisory number',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'PREVIOUS',
                        description: 'Optional: Tag of release this can upgrade FROM',
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
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-team-art@redhat.com',
                        ].join(',')
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

    buildlib.cleanWorkdir("${env.WORKSPACE}")

    try {
        sshagent(['aos-cd-test']) {
            // must be able to access remote registry for verification
            buildlib.registry_quay_dev_login()
            stage("versions") { release.stageVersions() }
            stage("validation") { release.stageValidation() }
            stage("payload") { release.stageGenPayload() }
            stage("tag stable") { release.stageTagStable() }
            stage("wait for stable") { release.stageWaitForStable() }
            stage("client sync") { release.stageClientSync() }
            stage("advisory update") { release.stageAdvisoryUpdate() }
            stage("cross ref check") { release.stageCrossRef() }
        }

        commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            from: "aos-cicd@redhat.com",
            subject: "Success building release payload: ${params.NAME}",
            body: """
Release Page: https://openshift-release.svc.ci.openshift.org/releasestream/4-stable/release/${params.NAME}
Quay PullSpec: quay.io/ocp/release:${params.NAME}
        """);
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-cicd@redhat.com",
            subject: "Error running OCP Release",
            body: "Encountered an error while running OCP release: ${err}");
        currentBuild.description = "Error while running OCP release:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}

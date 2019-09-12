#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    def quay_url = "quay.io/openshift-release-dev/ocp-release"

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
                        description: 'Build tag to pull from (e.g. 4.1.0-0.nightly-2019-04-22-005054)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'NAME',
                        description: 'Release name (e.g. 4.1.0)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'DESCRIPTION',
                        description: '[deprecated] Release description for metadata',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'ADVISORY',
                        description: 'Optional: Image release advisory number. If not given, the number will be retrived from ocp-build-data.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'PREVIOUS',
                        description: 'Optional: Tag(s) (comma separated) of last 10 releases this can upgrade FROM',
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
                            'aos-art-automation+new-release@redhat.com',
                        ].join(',')
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
            name = "${params.NAME}"
            from_release_tag = "${params.FROM_RELEASE_TAG}"
            description = "${params.DESCRIPTION}"
            advisory = params.ADVISORY? Integer.parseInt(params.ADVISORY.toString()) : 0
            previous = "${params.PREVIOUS}"
            String errata_url

            // must be able to access remote registry for verification
            buildlib.registry_quay_dev_login()
            stage("versions") { release.stageVersions() }
            stage("validation") {
                def retval = release.stageValidation(quay_url, name, advisory)
                advisory = advisory?:retval.advisoryInfo.id
                errata_url = retval.errataUrl
            }
            stage("payload") { release.stageGenPayload(quay_url, name, from_release_tag, description, previous, errata_url) }
            stage("tag stable") { release.stageTagRelease(quay_url, name) }
            stage("wait for stable") { release.stageWaitForStable() }
            stage("get release info") {
                release_info = release.stageGetReleaseInfo(quay_url, name)
            }
            stage("client sync") { release.stageClientSync('4-stable', 'ocp') }
            stage("advisory update") { release.stageAdvisoryUpdate() }
            stage("cross ref check") { release.stageCrossRef() }
        }

        dry_subject = ""
        if (params.DRY_RUN) { dry_subject = "[DRY RUN] "}

        commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "${dry_subject}Success building release payload: ${params.NAME}",
            body: """
Jenkins Job: ${env.BUILD_URL}
Release Page: https://openshift-release.svc.ci.openshift.org/releasestream/4-stable/release/${params.NAME}
Quay PullSpec: quay.io/openshift-release-dev/ocp-release:${params.NAME}

${release_info}
        """);
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Error running OCP Release",
            body: "Encountered an error while running OCP release: ${err}");
        currentBuild.description = "Error while running OCP release:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}

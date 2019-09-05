#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def buildlib = build.buildlib
    def commonlib = build.commonlib

    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: ''
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "aos-art-automation+new-signed-composes@redhat.com",
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'aos-art-automation+failed-signed-puddle@redhat.com',
                    ],
                    [
                        name: 'DRY_RUN',
                        description: 'Do not update the puddle. Just show what would have happened',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                ]
            ],
            disableConcurrentBuilds(),
        ]
    )

    commonlib.checkMock()
    def advisory = buildlib.elliott("--group=openshift-${params.BUILD_VERSION} get --use-default-advisory rpm --id-only", [capture: true]).trim()

    stage("Initialize") {
        buildlib.elliott "--version"
        buildlib.kinit()
        currentBuild.displayName = "#${currentBuild.number} OCP ${params.BUILD_VERSION}"
        build.initialize(advisory)
    }

    try {
        sshagent(["openshift-bot"]) {
            stage("Advisory is NEW_FILES") { build.signedComposeStateNewFiles() }
            stage("Attach builds") { build.signedComposeAttachBuilds() }
            stage("RPM diffs ran") { build.signedComposeRpmdiffsRan(advisory) }
            stage("RPM diffs resolved") { build.signedComposeRpmdiffsResolved(advisory) }
            stage("Advisory is QE") { build.signedComposeStateQE() }
            stage("Signing completing") { build.signedComposeRpmsSigned() }
            stage("New el7 compose") { build.signedComposeNewComposeEl7() }
            // Ensure the rhel8 tag script can read the required cert
            withEnv(['REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt']) {
                if (build.requiresRhel8()) {
                    stage("New el8 compose") { build.signedComposeNewComposeEl8() }
                }
            }
        }
        build.mailForSuccess()
    } catch (err) {
        currentBuild.description += "\n-----------------\n\n${err}\n-----------------\n"
        currentBuild.result = "FAILURE"

        if (params.MAIL_LIST_FAILURE.trim()) {
            commonlib.email(
                to: params.MAIL_LIST_FAILURE,
                from: "aos-art-automation+failed-signed-compose@redhat.com",
                replyTo: "aos-team-art@redhat.com",
                subject: "Error building OCP Signed Puddle ${params.BUILD_VERSION}",
                body:
                    """\
Pipeline build "${currentBuild.displayName}" encountered an error:
${currentBuild.description}
View the build artifacts and console output on Jenkins:
    - Jenkins job: ${commonlib.buildURL()}
    - Console output: ${commonlib.buildURL('console')}
"""
            )
        }
        throw err  // gets us a stack trace FWIW
    } finally {
        commonlib.safeArchiveArtifacts([
                'email/*',
                'shell/*',
                "${build.workdir}/changelog*.log",
                "${build.workdir}/puddle*.log",
            ]
        )
    }
}

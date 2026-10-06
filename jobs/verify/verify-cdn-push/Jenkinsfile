#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("verify-cdn-push", """
        Trigger CDN staging push for release advisories and poll until complete.
        Calls artcd verify-cdn-push which:
        1. Triggers CDN staging push for rpm and rhcos advisories via Errata API
        2. Polls until all push jobs reach COMPLETE status or timeout
        3. Fail fast on hard errors (API exceptions, FAILED push jobs)
        4. Keep polling on blocking advisory dependencies
    """)

    properties(
        [
            disableResume(),
            disableConcurrentBuilds(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '30',
                    daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION', '4plus'),
                    commonlib.artToolsParam(),
                    string(
                        name: 'ASSEMBLY',
                        description: 'Assembly name to verify (e.g. 4.22.9)',
                        defaultValue: "",
                        trim: true,
                    ),
                ]
            ],
        ]
    )

    if (currentBuild.description == null) {
        currentBuild.description = ""
    }

    try {

    sshagent(["openshift-bot"]) {
        stage("initialize") {
            currentBuild.displayName = "${params.BUILD_VERSION} - ${params.ASSEMBLY} - #${currentBuild.number}"
        }

        stage("verify-cdn-push") {
            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config=./config/artcd.toml",
            ]
            cmd += [
                "verify-cdn-push",
                "--version=${params.BUILD_VERSION}",
                "--assembly=${params.ASSEMBLY}",
            ]

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    string(credentialsId: 'art-bot-jenkins-gitlab', variable: 'GITLAB_TOKEN'),
                ]) {
                    withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                        buildlib.init_artcd_working_dir()
                        echo "Will run: ${cmd.join(' ')}"
                        sh(script: cmd.join(' '))
                    }
                }
            }
        }
    }

    } finally {
        commonlib.safeArchiveArtifacts([
            "artcd_working/**/*.log",
            "artcd_working/**/*.yaml",
            "artcd_working/**/*.yml",
            "artcd_working/**/*.json",
        ])
        buildlib.cleanWorkspace()
    }
    }
}

#!/usr/bin/env groovy

import org.jenkinsci.plugins.workflow.steps.FlowInterruptedException

def compressBrewLogs() {
    echo "Compressing brew logs.."
    commonlib.shell(script: "./find-and-compress-brew-logs.sh")
}

def isMassRebuild() {
    return currentBuild.displayName.contains("[mass rebuild]")
}

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    commonlib.describeJob("ocp4-konflux", """
        Build OCP 4 images with Konflux
    """)


    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '30',
                    daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                    commonlib.artToolsParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The name of an assembly to rebase & build for. If assemblies are not enabled in group.yml, this parameter will be ignored',
                        defaultValue: "test",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_PATH',
                        description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                        defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                        trim: true,
                    ),
                    string(
                        name: 'DOOZER_DATA_GITREF',
                        description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'IMAGE_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_IMAGES (e.g. logging-kibana5,openshift-jenkins-2)',
                        defaultValue: "",
                        trim: true,
                    ),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    if (currentBuild.description == null) {
        currentBuild.description = ""
    }
    sshagent(["openshift-bot"]) {
        stage("initialize") {
            currentBuild.displayName = "#${currentBuild.number}"
        }

        stage("ocp4") {
            // artcd command
            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config=./config/artcd.toml",
            ]
            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            cmd += [
                "beta:ocp4-konflux",
                "--version=${params.BUILD_VERSION}",
                "--assembly=${params.ASSEMBLY}",
            ]
            if (params.DOOZER_DATA_PATH) {
                cmd << "--data-path=${params.DOOZER_DATA_PATH}"
            }
            if (params.DOOZER_DATA_GITREF) {
                cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
            }
            cmd += [
                "--image-list=${commonlib.cleanCommaList(params.IMAGE_LIST)}"
            ]

            // Needed to detect manual builds
                wrap([$class: 'BuildUser']) {
                        builderEmail = env.BUILD_USER_EMAIL
                }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                            file(credentialsId: 'openshift-bot-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                ]){
                    withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']) {
                        sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
                        sh(script: cmd.join(' '), returnStdout: true)
                    }
                }
            }
        }
    }
}

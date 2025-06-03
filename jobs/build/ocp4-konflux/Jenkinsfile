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
                    booleanParam(
                        name: 'IGNORE_LOCKS',
                        description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                        defaultValue: false
                    ),
                    string(
                        name: 'PLR_TEMPLATE_COMMIT',
                        description: '(Optional) Override the Pipeline Run template commit from openshift-priv/art-konflux-template; Format is ghuser@commitish e.g. jupierce@covscan-to-podman-2',
                        defaultValue: "",
                        trim: true,
                    ),
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
                    choice(
                        name: 'IMAGE_BUILD_STRATEGY',
                        description: 'Which images are candidates for building? "only/except" refer to list below',
                        choices: [
                            "only",
                            "all",
                            "except",
                        ].join("\n")
                    ),
                    string(
                        name: 'IMAGE_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_IMAGES (e.g. logging-kibana5,openshift-jenkins-2)',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'SKIP_PLASHETS',
                        description: 'Do not build plashets (for example to save time when running multiple builds against test assembly)',
                        defaultValue: true,
                    ),
                    string(
                            name: 'LIMIT_ARCHES',
                            description: '(Optional) Limit included arches to this list. Valid values are (aarch64, ppc64le, s390x, x86_64)',
                            defaultValue: "",
                            trim: true,
                    ),
                    booleanParam(
                        name: 'SKIP_REBASE',
                        description: '(For testing) Skip the rebase step',
                        defaultValue: false
                    ),
                    booleanParam(
                        name: 'SKIP_BUNDLE_BUILD',
                        description: '(For testing) Skip the OLM bundle build step',
                        defaultValue: false,  // Default to true until we believe bundle build is stable.
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
            if (params.SKIP_PLASHETS) {
                cmd << "--skip-plashets"
            }
            if (params.LIMIT_ARCHES) {
                for (arch in params.LIMIT_ARCHES.split("[,\\s]+")) {
                    cmd << "--arch" << arch.trim()
                }
            }
            if (params.PLR_TEMPLATE_COMMIT) {
                cmd << "--plr-template=${params.PLR_TEMPLATE_COMMIT}"
            }
            cmd += [
                "--image-build-strategy=${params.IMAGE_BUILD_STRATEGY}",
                "--image-list=${commonlib.cleanCommaList(params.IMAGE_LIST)}"
            ]
            if (params.SKIP_REBASE) {
                cmd << "--skip-rebase"
            }
            if (params.IGNORE_LOCKS) {
                cmd << "--ignore-locks"
            }
            if (params.SKIP_BUNDLE_BUILD) {
                cmd << "--skip-bundle-build"
            }

            // Needed to detect manual builds
                wrap([$class: 'BuildUser']) {
                        builderEmail = env.BUILD_USER_EMAIL
                }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                            string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                            string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                            file(credentialsId: 'openshift-bot-ocp-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                            string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                            string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                            string(credentialsId: 'konflux-art-images-username', variable: 'KONFLUX_ART_IMAGES_USERNAME'),
                            string(credentialsId: 'konflux-art-images-password', variable: 'KONFLUX_ART_IMAGES_PASSWORD'),
                            file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS')
                ]){
                    withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']) {
                        buildlib.init_artcd_working_dir()
                        try {
                            sh(script: cmd.join(' '), returnStdout: true)
                        } catch (err) {
                            // If any image build/push failures occurred, mark the job run as unstable
                            currentBuild.result = "UNSTABLE"
                        }
                    }
                }
            }
        }

        stage("terminate") {
            commonlib.safeArchiveArtifacts([
                "artcd_working/**/*.log",
                "artcd_working/doozer_working/*.yaml",
                "artcd_working/doozer_working/*.yml",
            ])
            buildlib.cleanWorkspace()
        }
    }
}

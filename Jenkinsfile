#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("seed-lockfile", """
        <h2>Seed RPM lockfile generation for Konflux images</h2>
        <p>
        Builds components in the <b>test</b> assembly with <code>network_mode: open</code>
        to populate the DB with installed RPMs, then rebases in the target assembly
        (default: <b>stream</b>) with <code>--lockfile-seed-nvrs</code> so lockfile generation
        uses those builds' RPM data.
        </p>
        <p>
        You can skip the test build by providing pre-existing NVRs in <b>SEED_NVRS</b>,
        which is useful for cross-version seeding (e.g. using a 4.23 build for 4.22).
        </p>
    """)

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
                    commonlib.ocpVersionParam('BUILD_VERSION', '4plus'),
                    string(
                        name: 'IMAGE_LIST',
                        description: 'Comma-separated list of component names to seed lockfiles for (e.g. ironic,ovn-kubernetes)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'Target assembly for lockfile generation',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    string(
                        name: 'SEED_NVRS',
                        description: '(Optional) Pre-existing build NVRs to skip the test build. Format: name@NVR[,name@NVR,...]. Example: ironic@ironic-container-v4.22.0-assembly.test',
                        defaultValue: "",
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
                        name: 'LIMIT_ARCHES',
                        description: '(Optional) Limit included arches to this list. Valid values are (aarch64, ppc64le, s390x, x86_64)',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'PLR_TEMPLATE_COMMIT',
                        description: '(Optional) Override the Pipeline Run template commit from openshift-priv/art-konflux-template; Format is ghuser@commitish',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'BUILD_PRIORITY',
                        description: "Use default 'auto', to let doozer decide. If not, set a value from 1 (highest priority) to 10 (lowest priority).",
                        defaultValue: 'auto',
                        trim: true,
                    ),
                    string(
                        name: 'JIRA_KEY',
                        description: '(Optional) Jira ticket key to include in build title (e.g. ART-14902)',
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
            currentBuild.displayName = "#${currentBuild.number} - ${params.BUILD_VERSION}"
            if (params.SEED_NVRS) {
                currentBuild.displayName += " [seeded]"
            }
        }

        stage("seed-lockfile") {
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
                "seed-lockfile",
                "--version=${params.BUILD_VERSION}",
                "--assembly=${params.ASSEMBLY}",
                "--image-list=${commonlib.cleanCommaList(params.IMAGE_LIST)}",
            ]
            if (params.SEED_NVRS) {
                cmd << "--seed-nvrs=${params.SEED_NVRS.trim()}"
            }
            if (params.DOOZER_DATA_PATH) {
                cmd << "--data-path=${params.DOOZER_DATA_PATH}"
            }
            if (params.DOOZER_DATA_GITREF) {
                cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
            }
            if (params.LIMIT_ARCHES) {
                for (arch in params.LIMIT_ARCHES.split("[,\\s]+")) {
                    cmd << "--arch" << arch.trim()
                }
            }
            if (params.PLR_TEMPLATE_COMMIT) {
                cmd << "--plr-template=${params.PLR_TEMPLATE_COMMIT}"
            }
            if (params.BUILD_PRIORITY) {
                cmd << "--build-priority=${params.BUILD_PRIORITY}"
            }
            if (params.JIRA_KEY) {
                cmd << "--jira-key=${params.JIRA_KEY}"
            }

            wrap([$class: 'BuildUser']) {
                builderEmail = env.BUILD_USER_EMAIL
            }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    file(credentialsId: 'openshift-bot-ocp-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                    string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                    string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                    string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                    string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                    file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                    // redis not needed -- this pipeline runs without locks
                    file(credentialsId: 'konflux-art-images-auth-file', variable: 'KONFLUX_ART_IMAGES_AUTH_FILE'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                ]) {
                    withEnv([
                        "BUILD_USER_EMAIL=${builderEmail?: ''}",
                        "BUILD_URL=${BUILD_URL}",
                        "JOB_NAME=${JOB_NAME}",
                        'DOOZER_DB_NAME=art_dash',
                    ]) {
                        buildlib.init_artcd_working_dir()
                        sh(script: cmd.join(' '))
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
}

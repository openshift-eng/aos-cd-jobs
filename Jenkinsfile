#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    commonlib.describeJob("build-plashets", """
        <h2>Update OCP 4.y repos</h2>
        <b>Timing</b>: Usually run automatically from ocp4 and microshift-bootc.
        Humans may run as needed. Locks prevent conflicts.

        Creates new plashets if the automation is not frozen.
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
                    commonlib.ocpVersionParam('VERSION', '4'),
                    string(
                        name: 'RELEASE',
                        description: 'e.g. 201901011200.p?',
                        defaultValue: '',
                        trim: true,
                    ),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The name of the assembly to update repos for',
                        defaultValue: 'test',
                        trim: true,
                    ),
                    string(
                        name: 'REPOS',
                        description: '(Optional) Comma/space-separated list of repos to build to this list. If empty, build all repos. e.g. "rhel-8-server-ose-rpms"',
                        defaultValue: '',
                        trim: true,
                    ),
                    string(
                        name: 'DATA_PATH',
                        description: 'ocp-build-data fork to use (e.g. test customizations on your own fork)',
                        defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                        trim: true,
                    ),
                    string(
                        name: 'DATA_GITREF',
                        description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'COPY_LINKS',
                        description: 'Transform symlink into referent file/dir',
                        defaultValue: false,
                    ),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    stage("Initialize") {
        currentBuild.displayName = "${VERSION} - ${RELEASE} - ${ASSEMBLY}"

        if (params.DRY_RUN) {
            currentBuild.displayName += " [DRY_RUN]"
        }

        if (currentBuild.description == null) {
            currentBuild.description = ""
        }

    }

    stage("Build plashets") {
        buildlib.init_artcd_working_dir()
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
            "build-plashets",
            "--version=${params.VERSION}",
            "--release=${params.RELEASE}",
            "--assembly=${params.ASSEMBLY}"
        ]
        if (params.REPOS) {
            cmd << "--repos=${params.REPOS}"
        }
        if (params.DATA_PATH) {
            cmd << "--data-path=${params.DATA_PATH}"
        }
        if (params.DATA_GITREF) {
            cmd << "--data-gitref=${params.DATA_GITREF}"
        }
        if (params.COPY_LINKS) {
            cmd << "--copy-links"
        }

        try {
            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                    string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                    string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                ]) {
                    withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                        sh(script: cmd.join(' '), returnStdout: true)
                    }
                }
            }
        } catch (err) {
            currentBuild.description += "<hr />${err}"
            currentBuild.result = "FAILURE"
            throw err  // gets us a stack trace FWIW
        } finally {
            commonlib.safeArchiveArtifacts([
                "artcd_working/**/*.log",
                "artcd_working/doozer_working/*.yaml",
                "artcd_working/doozer_working/*.yml",
            ])
            buildlib.cleanWorkspace()
        }
    }
}

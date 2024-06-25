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

    commonlib.describeJob("ocp4", """
        <h2>Build OCP 4.y components incrementally</h2>
        <b>Timing</b>: Usually run automatically from merge_ocp.
        Humans may run as needed. Locks prevent conflicts.

        In typical usage, scans for changes that could affect package or image
        builds and rebuilds the affected components.  Creates new plashets if
        the automation is not frozen or if there are RPMs that are built in this run,
        and runs other jobs to sync builds to nightlies, create
        operator metadata, and sets MODIFIED bugs to ON_QA.

        May also build unconditionally or with limited components.
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
                    booleanParam(
                        name: 'IGNORE_LOCKS',
                        description: 'Do not wait for other builds in this version to complete (use only if you know they will not conflict)',
                        defaultValue: false
                    ),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'NEW_VERSION',
                        description: '(Optional) version for build instead of most recent\nor "+" to bump most recent version',
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
                    booleanParam(
                        name: 'PIN_BUILDS',
                        description: 'Build only specified rpms/images regardless of whether source has changed. WARNING: Disable this to use scan-sources as the source',
                        defaultValue: true,
                    ),
                    choice(
                        name: 'BUILD_RPMS',
                        description: 'Which RPMs are candidates for building? "only/except" refer to list below',
                        choices: [
                            "none",
                            "only",
                            "all",
                            "except",
                        ].join("\n"),
                    ),
                    string(
                        name: 'RPM_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_RPMS (e.g. openshift,openshift-kuryr)',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'BUILD_IMAGES',
                        description: 'Which images are candidates for building? "only/except" refer to list below',
                        choices: [
                            "only",
                            "none",
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
                    booleanParam(
                        name: 'COMMENT_ON_PR',
                        description: 'Comment on source PR after successful build',
                        defaultValue: false,
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List\naos-cicd@redhat.com,aos-qe@redhat.com',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-ocp4-build@redhat.com'
                        ].join(','),
                        trim: true
                    ),
                    string(
                        name: 'SPECIAL_NOTES',
                        description: '(Optional) special notes to include in the build email',
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

    try {

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
                    "ocp4",
                    "--version=${params.BUILD_VERSION}",
                    "--assembly=${params.ASSEMBLY}",
                ]
                if (params.DOOZER_DATA_PATH) {
                    cmd << "--data-path=${params.DOOZER_DATA_PATH}"
                }
                if (params.DOOZER_DATA_GITREF) {
                    cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
                }
                if (params.PIN_BUILDS) {
                    cmd << "--pin-builds"
                }
                if (params.COMMENT_ON_PR) {
                    cmd << "--comment-on-pr"
                }
                cmd += [
                    "--build-rpms=${params.BUILD_RPMS}",
                    "--rpm-list=${params.RPM_LIST}",
                    "--build-images=${params.BUILD_IMAGES}",
                    "--image-list=${commonlib.cleanCommaList(params.IMAGE_LIST)}"
                ]
                if (params.SKIP_PLASHETS) {
                    cmd << "--skip-plashets"
                }
                if (params.IGNORE_LOCKS) {
                    cmd << "--ignore-locks"
                }

                // Needed to detect manual builds
                wrap([$class: 'BuildUser']) {
                        builderEmail = env.BUILD_USER_EMAIL
                    }

                buildlib.withAppCiAsArtPublish() {
                    withCredentials([
                                string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                                string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                                string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                                string(credentialsId: 'redis-host', variable: 'REDIS_HOST'),
                                string(credentialsId: 'redis-port', variable: 'REDIS_PORT'),
                                string(credentialsId: 'gitlab-ocp-release-schedule-schedule', variable: 'GITLAB_TOKEN'),
                                string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                                string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                                aws(credentialsId: 's3-art-srv-enterprise', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'),
                                string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                                usernamePassword(credentialsId: 'art-dash-db-login', passwordVariable: 'DOOZER_DB_PASSWORD', usernameVariable: 'DOOZER_DB_USER'),
                                file(credentialsId: "art-cluster-art-cd-pipeline-kubeconfig", variable: 'ART_CLUSTER_ART_CD_PIPELINE_KUBECONFIG'),
                            ]) {
                        withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}", 'DOOZER_DB_NAME=art_dash']) {
                            sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
                            sh(script: cmd.join(' '), returnStdout: true)
                        }
                    }
                }
            }

            stage("terminate") {
                // If any image build/push failures occurred, mark the job run as unstable
                def record_log = buildlib.parse_record_log("artcd_working/doozer_working/")
                builds = record_log.get('build', [])
                for (i = 0; i < builds.size(); i++) {
                    bld = builds[i]
                    if (bld['status'] != '0' || bld['push_status'] != '0') {
                        currentBuild.result = "UNSTABLE"
                    }
                }
            }
        }
    } catch (err) {
        if (params.MAIL_LIST_FAILURE.trim()) {
            commonlib.email(
                to: params.MAIL_LIST_FAILURE,
                from: "aos-team-art@redhat.com",
                subject: "Error building OCP ${params.BUILD_VERSION}",
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
        currentBuild.description += "<hr />${err}"
        currentBuild.result = "FAILURE"
        throw err  // gets us a stack trace FWIW
    } finally {
        compressBrewLogs()
        commonlib.safeArchiveArtifacts([
            "artcd_working/doozer_working/*.log",
            "artcd_working/doozer_working/brew-logs.tar.bz2",
            "artcd_working/doozer_working/*.yaml",
            "artcd_working/doozer_working/*.yml",
        ])
        buildlib.cleanWorkspace()
    }
}

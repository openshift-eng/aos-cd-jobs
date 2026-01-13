#!/usr/bin/env groovy

node() {
    timestamps {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("build-sync-multi", """
        <h2>Multi-model payload sync for 4.y images</h2>
        <b>Timing</b>: Usually automated via scheduled job. Human might use to manually trigger.

        This job generates multi-model payloads using Konflux-built images. Multi-model payloads
        combine images from different architectures into a single heterogeneous release.

        Unlike regular build-sync, this creates payloads where the base architecture can be
        specified (e.g., amd64:0 means use the latest amd64 nightly as the base).

        For more details see the <a href="https://github.com/openshift-eng/aos-cd-jobs/blob/master/jobs/build/build-sync-multi/README.md" target="_blank">README</a>
    """)

    // Please update README.md if modifying parameter names or semantics
    properties([
        disableResume(),
        buildDiscarder(
          logRotator(
              artifactDaysToKeepStr: '30',
              daysToKeepStr: '30',
              numToKeepStr: '300',
          )
        ),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                commonlib.suppressEmailParam(),
                commonlib.mockParam(),
                commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                commonlib.artToolsParam(),
                string(
                    name: 'ASSEMBLY',
                    description: 'The name of an assembly to sync.',
                    defaultValue: "stream",
                    trim: true,
                ),
                string(
                    name: 'MULTI_MODEL',
                    description: 'Multi-model specification (e.g. "amd64:0" for latest amd64 nightly as base)',
                    defaultValue: "amd64:0",
                    trim: true,
                ),
                string(
                    name: 'DOOZER_DATA_PATH',
                    description: 'ocp-build-data fork to use (e.g. assembly definition in your own fork)',
                    defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                    trim: true,
                ),
                booleanParam(
                    name        : 'EMERGENCY_IGNORE_ISSUES',
                    description : ['Ignore all issues with constructing payload.',
                                   'In gen-payload, viable will be true whatever is the case,',
                                   'allowing internal inconsistencies.',
                                   'Only supported for assemblies of type Stream.<br/>',
                                   '<b/>Do not use without approval.</b>'].join(' '),
                    defaultValue: false,
                ),
                string(
                    name: 'DOOZER_DATA_GITREF',
                    description: '(Optional) Doozer data path git [branch / tag / sha] to use',
                    defaultValue: "",
                    trim: true,
                ),
                booleanParam(
                    name        : 'DRY_RUN',
                    description : 'Run "oc" commands with the dry-run option set to true',
                    defaultValue: false,
                ),
                string(
                    name        : 'EXCLUDE_ARCHES',
                    description : '(Optional) List of problem arch(es) NOT to sync (aarch64, ppc64le, s390x, x86_64)',
                    defaultValue: "",
                    trim: true,
                ),
                booleanParam(
                    name        : 'EMBARGO_PERMIT_ACK',
                    description : 'WARNING: Only enable this if a payload containing embargoed build(s) is being promoted after embargo lift',
                    defaultValue: false,
                ),
                commonlib.enableTelemetryParam(),
                commonlib.telemetryEndpointParam(),
            ],
        ]
    ])  // Please update README.md if modifying parameter names or semantics

    commonlib.checkMock()

    stage("Initialize") {
        echo("Initializing ${params.BUILD_VERSION} multi-model sync: #${currentBuild.number}")
        currentBuild.displayName = "${BUILD_VERSION} - ${ASSEMBLY} [MULTI-MODEL]"

        // doozer_working must be in WORKSPACE in order to have artifacts archived
        mirrorWorking = "${env.WORKSPACE}/MIRROR_working"
        buildlib.cleanWorkdir(mirrorWorking)

        if (params.DRY_RUN) {
            currentBuild.displayName += " [DRY_RUN]"
        }

        def arches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}").toList()
        if ( params.EXCLUDE_ARCHES ) {
            excludeArches = commonlib.parseList(params.EXCLUDE_ARCHES)
            currentBuild.displayName += " [EXCLUDE ${excludeArches.join(', ')}]"
            if ( !arches.containsAll(excludeArches) )
                error("Trying to exclude arch ${excludeArches} not present in known arches ${arches}")
            arches.removeAll(excludeArches)
        }

        if (currentBuild.description == null) {
            currentBuild.description = ""
        }
        currentBuild.description += "Arches: ${arches.join(', ')}<br>Multi-model: ${params.MULTI_MODEL}"
    }

    stage("Version dumps") {
        buildlib.doozer "--version"
        buildlib.elliott "--version"
        buildlib.oc("version --client=true -o yaml")
    }

    stage ("build-sync-multi") {
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
            "build-sync-multi",
            "--version=${params.BUILD_VERSION}",
            "--assembly=${params.ASSEMBLY}",
            "--multi-model=${params.MULTI_MODEL}",
        ]
        cmd << "--data-path=${params.DOOZER_DATA_PATH}"
        if (params.EMERGENCY_IGNORE_ISSUES) {
            cmd << "--emergency-ignore-issues"
        }
        if (params.DOOZER_DATA_GITREF) {
            cmd << "--data-gitref=${params.DOOZER_DATA_GITREF}"
        }
        if (params.EXCLUDE_ARCHES) {
            cmd << "--exclude-arches=${commonlib.cleanCommaList(params.EXCLUDE_ARCHES)}"
        }
        if (params.EMBARGO_PERMIT_ACK) {
            cmd << "--embargo-permit-ack"
        }

        // Run pipeline
        echo "Will run ${cmd.join(' ')}"

        try {
            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                    string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                    string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    file(credentialsId: 'konflux-art-images-auth-file', variable: 'KONFLUX_ART_IMAGES_AUTH_FILE'),
                ]) {
                    def envVars = ["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]
                    if (params.TELEMETRY_ENABLED) {
                        envVars << "TELEMETRY_ENABLED=1"
                        if (params.OTEL_EXPORTER_OTLP_ENDPOINT && params.OTEL_EXPORTER_OTLP_ENDPOINT != "") {
                            envVars << "OTEL_EXPORTER_OTLP_ENDPOINT=${params.OTEL_EXPORTER_OTLP_ENDPOINT}"
                        }
                    }
                    withEnv(envVars) {
                        sh(script: cmd.join(' '), returnStdout: true)
                    }
                }
            }

        } catch (err) {
            commonlib.email(
                    to: "aos-art-automation+failed-build-sync-multi@redhat.com",
                    from: "aos-art-automation@redhat.com",
                    replyTo: "aos-team-art@redhat.com",
                    subject: "Error during OCP ${params.BUILD_VERSION} multi-model build sync",
                    body: """
    There was an issue running build-sync-multi for OCP ${params.BUILD_VERSION}:

        ${err}
    """)
            throw (err)
        } finally {
            commonlib.safeArchiveArtifacts([
                "gen-payload-artifacts/*",
                "MIRROR_working/debug.log",
                "artcd_working/**/*.log",
            ])
            buildlib.cleanWorkspace()
        }
    } // stage build-sync-multi
    }
}


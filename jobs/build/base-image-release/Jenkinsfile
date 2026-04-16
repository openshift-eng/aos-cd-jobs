#!/usr/bin/env groovy

node() {
    timestamps {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("base-image-release", """
        <h2>Release base images to base repository</h2>
        <b>Timing</b>: This is only ever run by humans, as needed. No job should be calling it.

        This job takes a list of built base images (like openshift-enterprise-base-rhel9, golang builders)
        and releases them to the base repository using the doozer images:release-to-base-repo command.
        
        The job requires a comma-separated list of NVRs to perform batch release operations.
    """)

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
                string(
                    name: 'BUILD_VERSION',
                    description: 'Build group name (e.g., openshift-5.0 for OCP or rhel-9-golang-1.24 for golang builders)',
                    defaultValue: "openshift-5.0",
                    trim: true,
                ),
                commonlib.artToolsParam(),
                string(
                    name: 'ASSEMBLY',
                    description: 'The name of an assembly to use.',
                    defaultValue: "stream",
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
                    name: 'NVRS',
                    description: 'Comma-separated list of NVRs to release (e.g. openshift-enterprise-base-rhel9-container-v4.22.0-..., golang-1.21-container-v4.22.0-...)',
                    defaultValue: "",
                    trim: true,
                ),
                booleanParam(
                    name: 'DRY_RUN',
                    description: 'Run in dry-run mode without making actual changes',
                    defaultValue: false,
                ),
            ],
        ]
    ])

    commonlib.checkMock()

    stage('Validate Parameters') {
        if (!params.NVRS) {
            error("NVRS parameter is required. Please specify a comma-separated list of NVRs to release")
        }
        
        def nvrList = params.NVRS.split(',').collect { it.trim() }.findAll { !it.isEmpty() }
        def nvrCount = nvrList.size()
        
        echo("Base Image Release Parameters:")
        echo("  BUILD_VERSION: ${params.BUILD_VERSION}")
        echo("  ASSEMBLY: ${params.ASSEMBLY}")
        echo("  NVRS: ${params.NVRS}")
        echo("  NVR Count: ${nvrCount}")
        echo("  DRY_RUN: ${params.DRY_RUN}")
        
        currentBuild.displayName = "${params.BUILD_VERSION} - ${nvrCount} NVRs"
        if (params.DRY_RUN) {
            currentBuild.displayName += " [DRY_RUN]"
        }
    }

    stage("Version dumps") {
        buildlib.doozer "--version"
        buildlib.elliott "--version"
        buildlib.oc("version --client=true -o yaml")
    }

    stage("Release base image") {
        doozer_working = "${env.WORKSPACE}/doozer_working"
        buildlib.cleanWorkdir(doozer_working)
        
        def nvrList = params.NVRS.split(',').collect { it.trim() }.findAll { !it.isEmpty() }
        def nvrCount = nvrList.size()
        
        try {
            def cmd = [
                "doozer",
                "--group", "${params.BUILD_VERSION}",
                "--assembly", "${params.ASSEMBLY}"
            ]
            
            if (params.DOOZER_DATA_PATH) {
                cmd += ["--data-path", "${params.DOOZER_DATA_PATH}"]
            }
            
            if (params.DOOZER_DATA_GITREF) {
                cmd += ["--data-gitref", "${params.DOOZER_DATA_GITREF}"]
            }
            
            cmd += [
                "images:release-to-base-repo",
                "--nvrs", "${params.NVRS}"
            ]
            
            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }

            echo "Will run: ${cmd.join(' ')}"
            
            dir(doozer_working) {
                withCredentials([
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    string(credentialsId: 'openshift-art-build-bot-app-id', variable: 'GITHUB_APP_ID'),
                    file(credentialsId: 'openshift-art-build-bot-private-key.pem', variable: 'GITHUB_APP_PRIVATE_KEY_PATH'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    file(credentialsId: 'openshift-bot-ocp-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                    file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                    usernamePassword(
                        credentialsId: 'art-dash-db-login',
                        passwordVariable: 'DOOZER_DB_PASSWORD',
                        usernameVariable: 'DOOZER_DB_USER'
                    ),
                ]) {
                    withEnv(['DOOZER_DB_NAME=art_dash', "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                        sh(script: cmd.join(' '), returnStdout: true)
                    }
                }
            }
            
        } catch (err) {
            commonlib.email(
                    to: "aos-art-automation+failed-base-image-release@redhat.com",
                    from: "aos-art-automation@redhat.com",
                    replyTo: "aos-team-art@redhat.com",
                    subject: "Error during base image release for ${nvrCount} NVRs",
                    body: """
There was an issue releasing base images:

    NVRs: ${params.NVRS}
    Error: ${err}

Build URL: ${BUILD_URL}
""")
            throw (err)
        } finally {
            commonlib.safeArchiveArtifacts([
                "doozer_working/debug.log",
                "doozer_working/**/*.log",
                "doozer_working/**/*.json",
            ])
            buildlib.cleanWorkspace()
        }
    }

    }
}
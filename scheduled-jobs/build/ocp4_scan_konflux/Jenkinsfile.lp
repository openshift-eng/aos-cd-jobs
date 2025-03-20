node {
    checkout scm
    buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib
    slacklib = commonlib.slacklib

    properties( [
        buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '100', daysToKeepStr: '', numToKeepStr: '100')),
        disableConcurrentBuilds(),
        disableResume(),
        [
            $class: "ParametersDefinitionProperty",
            parameterDefinitions: [
                commonlib.artToolsParam(),
                commonlib.mockParam(),
            ]
        ]
    ] )

    commonlib.checkMock()
    buildlib.init_artcd_working_dir()

    stage("scan") {
        cmd = [
            "artcd",
            "-vv",
            "--working-dir=${WORKSPACE}/artcd_working",
            "--config=./config/artcd.toml",
            "schedule-ocp4-scan-konflux"
        ]
        for ( version in commonlib.ocp4Versions ) {
            // Only build OCP versions < 4.17
            if (commonlib.cmp_version(version, "4.17") == -1) {
                cmd << "--version=${version}"
            }
        }

        withCredentials([
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD')]) {
            wrap([$class: 'BuildUser']) {
                builderEmail = env.BUILD_USER_EMAIL
            }

            withEnv(["BUILD_USER_EMAIL=${builderEmail?: ''}", "BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                try {
                    echo "Will run ${cmd}"
                    sh(script: cmd.join(' '), returnStdout: true)
                } catch (err) {
                    slacklib.to("#art-release").failure("Error running ocp_scan", err)
                    throw err
                }
            }
        }

    }
}

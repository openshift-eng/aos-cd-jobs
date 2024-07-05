
node() {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    slacklib = commonlib.slacklib

    properties([
        buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '100')),
        disableConcurrentBuilds(),
        disableResume(),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                string(
                        name: 'CHANNEL',
                        description: 'Where should we notify about ART threads',
                        trim: true,
                        defaultValue: "#team-art"
                    ),
                    booleanParam(
                        name: 'DRY_RUN',
                        description: 'Will not message to slack, if dry run is true',
                        defaultValue: false
                    ),
                commonlib.mockParam(),
            ]
        ]
    ])

    commonlib.checkMock()

    stage('Check unresolved ART threads') {
        try {
            withCredentials([
                                string(credentialsId: "art-bot-slack-token", variable: "SLACK_API_TOKEN"),
                                string(credentialsId: "art-bot-slack-user-token", variable: "SLACK_USER_TOKEN"),
                                string(credentialsId: "art-bot-slack-signing-secret", variable: "SLACK_SIGNING_SECRET"),
                                string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                                string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN')
                            ]) {
                withEnv(["CHANNEL=${params.CHANNEL}", "DRY_RUN=${params.DRY_RUN}"]) {
                    retry(10) {
                        commonlib.shell(script: "python -- scheduled-jobs/scanning/art-notify/art-notify.py")
                    }
                }
            }
        } catch (e) {
            slacklib.to('#team-art').say("Error while checking unresolved threads: ${env.BUILD_URL}")
            throw(e)
        }
    }
}

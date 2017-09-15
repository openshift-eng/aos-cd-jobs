#!/usr/bin/env groovy

/**
 * sprint_tools states that sprints end on Friday. After 12pm, it will report 0
 * days remaining in the sprint. On Saturday (12pm), you will see the sprint having
 * reset to 20 days remaining.
 */
DEV_CUT_DAY_LEFT = 9  // Second Wednesday
STAGE_CUT_DAYS_LEFT = 3  // Third Tuesday
LIFT_STAGE_CUT_DAYS_LEFT = 19  // First Sunday

properties(
        [
            buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '360')),
            pipelineTriggers([cron('00 20 * * *')]),
            [$class : 'ParametersDefinitionProperty',
          parameterDefinitions:
                  [
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'openshift-build-1', description: 'Jenkins agent node', name: 'TARGET_NODE'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                          [$class: 'hudson.model.TextParameterDefinition', defaultValue: "", description: 'Include special notes in the notification email?', name: 'SPECIAL_NOTES'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Pretend it is DevCut START?', name: 'TEST_DEV_CUT'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Pretend it is StageCut START?', name: 'TEST_STAGE_CUT'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Pretend it is StageCut END?', name: 'TEST_LIFT_STAGE_CUT'],
                  ]
            ],
            disableConcurrentBuilds()
        ]
)

IS_TEST_MODE = TEST.toBoolean()

def mail_success( phase, body ) {

    if ( SPECIAL_NOTES != "" ) {
        body += "\n\nImportant Notification\n-------------------------------------\n${SPECIAL_NOTES}\n"
    }

    mail(
            to: "${MAIL_LIST_SUCCESS}",
            from: "aos-cd@redhat.com",
            replyTo: 'jupierce@redhat.com',
            subject: "[aos-announce] Sprint Phase: ${phase} (Sprint " + SPRINT_ID + ")",
            body: "${body}");
}

node(TARGET_NODE) {

    checkout scm

    def commonlib = load( "pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    try {


        DEV_CUT_BODY = readFile( "emails/devcut_start" )

        STAGE_CUT_BODY = readFile( "emails/stagecut_start" )

        REOPEN_BODY = readFile( "emails/open_master" )

        sshagent([SSH_KEY_ID]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot
            tmpd = pwd tmp: true
            dir(tmpd) {
                // Setup sprint tools (requires openshift-bot credentials)
                sh "git clone --depth 1 git@github.com:openshift/sprint_tools.git"
                sh "git clone --depth 1 git@github.com:openshift/trello_config.git"
                sh "cp -r trello_config/trello/* sprint_tools/"

                dir("trello_config") {
                    SPRINT_ID = sh(returnStdout: true, script: "./trello sprint_identifier").trim()
                    DAYS_LEFT_IN_SPRINT = sh(returnStdout: true, script: "./trello days_left_in_sprint").trim()
                }

                if ( DAYS_LEFT_IN_SPRINT == DEV_CUT_DAY_LEFT ) {
                    mail_success("Start of DevCut", DEV_CUT_BODY)
                }

                if ( DAYS_LEFT_IN_SPRINT == STAGE_CUT_DAYS_LEFT ) {
                    mail_success("Start of StageCut", STAGE_CUT_BODY)
                }

                if ( DAYS_LEFT_IN_SPRINT == LIFT_STAGE_CUT_DAYS_LEFT ) {
                    mail_success("Master Open", REOPEN_BODY)
                }

                deleteDir()
            }
        }

    } catch ( err ) {
        mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-cd@redhat.com",
                subject: "Error running sprint control",
                body: """${err}

    Jenkins job: ${env.BUILD_URL}
    """);
        throw err
    }


}

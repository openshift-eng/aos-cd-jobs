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
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'https://api.ci.openshift.org:443', description: 'OpenShift CI Server', name: 'CI_SERVER'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-announce@redhat.com', description: 'Success Announce List', name: 'MAIL_LIST_ANNOUNCE'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-leads@redhat.com', description: 'Success List List', name: 'MAIL_LIST_LEADS'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                          [$class: 'hudson.model.TextParameterDefinition', defaultValue: "", description: 'Include special notes in the notification email?', name: 'SPECIAL_NOTES'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Pretend it is DevCut START?', name: 'TEST_DEV_CUT'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Pretend it is StageCut START?', name: 'TEST_STAGE_CUT'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Pretend it is master open?', name: 'TEST_OPEN_MASTER'],
                  ]
            ],
            disableConcurrentBuilds()
        ]
)

TEST_DEV_CUT = TEST_DEV_CUT.toBoolean()
TEST_STAGE_CUT = TEST_STAGE_CUT.toBoolean()
TEST_OPEN_MASTER = TEST_OPEN_MASTER.toBoolean()

TEST_ONLY = TEST_DEV_CUT || TEST_STAGE_CUT || TEST_OPEN_MASTER

if ( TEST_ONLY ) {
    if ( MAIL_LIST_ANNOUNCE.contains( "aos" ) || MAIL_LIST_LEADS.contains( "aos" ) ) {
        error "Set success list to non-mailing list when testing"
    }
}

def sprint_announce(phase, body) {

    if ( SPECIAL_NOTES != "" ) {
        body += "\n\nImportant Notification\n-------------------------------------\n${SPECIAL_NOTES}\n"
    }

    mail(
            to: "${MAIL_LIST_ANNOUNCE}",
            from: "aos-cd@redhat.com",
            replyTo: 'jupierce@redhat.com',
            subject: "[aos-announce] Sprint Phase: ${phase} (Sprint ${SPRINT_ID})",
            body: "${body}");
}

def release_announce(phase, body) {

    if ( SPECIAL_NOTES != "" ) {
        body += "\n\nImportant Notification\n-------------------------------------\n${SPECIAL_NOTES}\n"
    }

    mail(
            to: "${MAIL_LIST_ANNOUNCE}",
            from: "aos-cd@redhat.com",
            replyTo: 'jupierce@redhat.com',
            subject: "[aos-announce] Release Phase: ${phase}",
            body: "${body}");
}


def mail_leads(body) {

    mail(
            to: "${MAIL_LIST_LEADS}",
            from: "aos-cd@redhat.com",
            replyTo: 'jupierce@redhat.com',
            subject: "[aos-leads] Online First Support Assignments (Sprint ${SPRINT_ID})",
            body: "${body}");
}

node(TARGET_NODE) {

    checkout scm

    def commonlib = load( "pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    try {

        FEATURE_COMPLETE_BODY = readFile( "emails/feature_complete" )

        DEV_CUT_BODY = readFile( "emails/devcut_start" )

        STAGE_CUT_BODY = readFile( "emails/stagecut_start" )

        REOPEN_BODY = readFile( "emails/open_master" )

        SIGNUP_BODY = readFile( "emails/online_first_signup" )

        sshagent(["openshift-bot"]) {
            // To work on real repos, buildlib operations must run with the permissions of openshift-bot
            tmpd = pwd tmp: true
            dir(tmpd) {
                // Jenkins will reuse temp directories if the job does not make it to deleteDir() :(
                sh "rm -rf sprint_tools"  
                sh "rm -rf trello_config"  

                // Setup sprint tools (requires openshift-bot credentials)
                sh "git clone --depth 1 git@github.com:openshift/sprint_tools.git"
                sh "git clone --depth 1 git@github.com:openshift/trello_config.git"
                sh "cp -r trello_config/trello/* sprint_tools/"

                dir("sprint_tools") {
                    SPRINT_ID = sh(returnStdout: true, script: "./trello sprint_identifier").trim().toInteger()
                    DAYS_LEFT_IN_SPRINT = sh(returnStdout: true, script: "./trello days_left_in_sprint").trim().toInteger()
                    DAYS_LEFT_UNTIL_FEATURE_COMPLETE = sh(returnStdout: true, script: "./trello days_until_feature_complete").trim().toInteger()

                }

                echo "Detected ${DAYS_LEFT_IN_SPRINT} days left in sprint"
                echo "Days left until feature complete: ${DAYS_LEFT_UNTIL_FEATURE_COMPLETE}"

                MERGE_GATE_LABELS=null

                FC = (DAYS_LEFT_UNTIL_FEATURE_COMPLETE <= 0)

                if ( DAYS_LEFT_UNTIL_FEATURE_COMPLETE == 0 ) {
                    release_announce("Feature Complete", FEATURE_COMPLETE_BODY)
                    MERGE_GATE_LABELS="kind/bug"

                } else if ( DAYS_LEFT_UNTIL_FEATURE_COMPLETE > 0 ) {

                    if ( DAYS_LEFT_IN_SPRINT == DEV_CUT_DAY_LEFT || TEST_DEV_CUT ) {
                        sprint_announce("Start of DevCut", DEV_CUT_BODY)
                        MERGE_GATE_LABELS="kind/bug"
                    }

                    if ( DAYS_LEFT_IN_SPRINT == LIFT_STAGE_CUT_DAYS_LEFT || TEST_OPEN_MASTER ) {
                        sprint_announce("Master Open", REOPEN_BODY)
                        mail_leads(SIGNUP_BODY)
                        MERGE_GATE_LABELS = ""
                    }

                }

                // Stagecut should happen regardless of feature complete
                if ( DAYS_LEFT_IN_SPRINT == STAGE_CUT_DAYS_LEFT || TEST_STAGE_CUT ) {
                    sprint_announce("Start of StageCut", STAGE_CUT_BODY)
                    MERGE_GATE_LABELS="kind/bug"
                }

                // If there is a change to be made
                if ( MERGE_GATE_LABELS != null ) {
                    b = build       job: './merge-gating', propagate: true,
                            parameters: [
                                    [$class: 'StringParameterValue', name: 'MERGE_GATE_LABELS', value: "${MERGE_GATE_LABELS}"],
                                    [$class: 'BooleanParameterValue', name: 'TEST_ONLY', value: TEST_ONLY],
                            ]

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

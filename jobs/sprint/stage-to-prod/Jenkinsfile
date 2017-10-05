#!/usr/bin/env groovy

MAIL_FROM = 'aos-cd@redhat.com'
REPLY_TO = 'jupierce@redhat.com'

repos = [
    //  repo-name: repo-path within /srv/enterprise
    OCP:           'online',
    OnlineScripts: 'online-openshift-scripts'
]

properties([
        [ $class : 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    name: 'CONTENT',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: repos.keySet().join('\n'),
                    defaultValue: 'OCP',
                    description: 'Select the content to promote'
                ],
                [
                    name: 'MODE',
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: ['interactive', 'automatic', 'quiet'].join('\n'),
                    defaultValue: 'interactive',
                    description: 'Select automatic to prevent confirmation prompt. Select quiet to prevent notification emails (implies automatic).'
                ],
                [
                    name: 'MAIL_LIST_SUCCESS',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'jupierce@redhat.com,smunilla@redhat.com',
                    description: 'Success Mailing List'
                ],
                [
                    name: 'MAIL_LIST_FAILURE',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'jupierce@redhat.com,smunilla@redhat.com',
                    description: 'Failure Mailing List'
                ],
                [
                    name: 'MOCK',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false,
                    description: 'Mock run to pickup new Jenkins parameters?',
                ],
                [
                    name: 'TARGET_NODE',
                    description: 'Jenkins agent node',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'openshift-build-1'
                ],
            ]
        ]
    ]
)

def mail_success() {
    if ( MODE != 'quiet' ) {
        mail(
            to: "${MAIL_LIST_SUCCESS}",
            from: MAIL_FROM,
            replyTo: REPLY_TO,
            subject: "Stage has been synced to prod for: ${CONTENT}",
            body: """
For details see the jenkins job.
Jenkins job: ${env.BUILD_URL}
""");
    }
}

def mail_failure = { err ->
    if ( MODE != 'quiet' ) {
        mail(
            to: "${MAIL_LIST_FAILURE}",
            from: MAIL_FROM,
            replyTo: REPLY_TO,
            subject: "Error syncing stage to prod on mirrors for: ${CONTENT}",
            body: """Encoutered an error while syncing stage to prod on mirrors: ${err}

Jenkins job: ${env.BUILD_URL}
""");
    }
}

def try_wrapper(failure_func, f) {
    try {
        f.call()
    } catch (err) {
        failure_func(err)
        // Re-throw the error in order to fail the job
        throw err
    }
}

node(TARGET_NODE) {

    checkout scm
    def buildlib = load( "pipeline-scripts/buildlib.groovy" )

    try_wrapper(mail_failure) {

        stage('Confirm') {
            repo = repos[CONTENT]
            echo "Latest ${CONTENT} will be promoted from stage (${repo}-stg) to production (${repo}-prod)."
            if ( MODE != "automatic" ) {
                input "Do you want to proceed?"
            }
        }

        stage('Stage to Prod') {
            sshagent(['openshift-bot']) { // errata puddle must run with the permissions of openshift-bot to succeed
                buildlib.invoke_on_rcm_guest('mirrors-stage-to-prod.sh', repo)
            }
            mail_success()
        }
    }
}

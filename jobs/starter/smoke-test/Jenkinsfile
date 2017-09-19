#!/usr/bin/env groovy

// A Job to run a smoke test in a cluster
// 
// It invokes the 'smoketest' operation of 'cicd-control.sh' for the specified cluster.
// Optionally emails test results.

@Library('aos_cd_ops') _

// Ask the shared library which clusters this job should act on
cluster_choice = aos_cd_ops_data.getClusterList("${env.BRANCH_NAME}").join("\n")  // Jenkins expects choice parameter to be linefeed delimited

properties([
        [   $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: "${cluster_choice}",
                    name: 'CLUSTER_SPEC',
                    description: 'Cluster to run tests on',
                ],
                [
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false,
                    description: 'Send email notifications',
                    name: 'MAIL_RESULTS'
                ],
                [
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'aos-cicd@redhat.com',
                    description: 'Success Mailing List',
                    name: 'MAIL_LIST_SUCCESS'
                ],
                [
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'aos-qe@redhat.com',
                    description: 'Failure Mailing List',
                    name: 'MAIL_LIST_FAILURE'
                ],
            ]
        ],
    ]
)

node('openshift-build-1') {
    checkout scm
        
    def deploylib = load( "pipeline-scripts/deploylib.groovy" )
    deploylib.initialize(CLUSTER_SPEC)

    try {

        stage( 'smoketest' ) {
            sshagent([CLUSTER_ENV]) {
                smoketest = deploylib.run("smoketest", null, true)
                echo smoketest
            }
        }

        if ( MAIL_RESULTS.toBoolean() ) {
            mail(
                to: "${MAIL_LIST_SUCCESS}",
                from: "aos-cd@redhat.com",
                replyTo: 'jupierce@redhat.com',
                subject: "Cluster smoke test succeeded: ${CLUSTER_NAME}",
                body: """\
Jenkins job: ${env.BUILD_URL}

Smoke test output:
${smoketest}
""");

        }

    } catch ( err ) {
        if ( MAIL_RESULTS.toBoolean() ) {
            mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-cd@redhat.com",
                subject: "Error during smoke test on cluster ${CLUSTER_NAME}",
                body: """Encountered an error: ${err}

Jenkins job: ${env.BUILD_URL}

Smoke test output:
${smoketest}
""");
        }

        // Re-throw the error in order to fail the job
        throw err
    }

}

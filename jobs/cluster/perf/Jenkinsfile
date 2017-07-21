#!/usr/bin/env groovy

def mail_success(list) {
    mail(
        to: "${list}",
        from: "aos-cd@redhat.com",
        replyTo: 'jupierce@redhat.com',
        subject: "Cluster Performance Test(${OPERATION}) complete: ${CLUSTER_NAME}",
        body: """\
Jenkins job: ${env.BUILD_URL}
""");
}

node('openshift-build-1') {

    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jeder@redhat.com, vlaad@redhat.com, mifiedle@redhat.com, jupierce@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'mifiedle@redhat.com, jupierce@redhat.com, vlaad@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "test-key\ncicd\ndev-preview-int\ndev-preview-stg\npreview\nfree-int\nfree-stg\nstarter-us-east-1\nstarter-us-east-2\nstarter-us-west-2", name: 'CLUSTER_NAME', description: 'The name of the cluster to target'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "perf1\nperf2\nperf3", name: 'OPERATION', description: 'Test to perform'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "interactive\nquiet\nsilent\nautomatic", name: 'MODE', description: 'Select automatic to prevent input prompt. Select quiet to prevent aos-devel emails. Select silent to prevent any success email.'],
                      ]
             ]]
    )

    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}], CLUSTER_NAME:${CLUSTER_NAME}, OPERATION:${OPERATION}, MODE:${MODE}"

    currentBuild.displayName = "#${currentBuild.number} - ${OPERATION} ${CLUSTER_NAME}"
    
    if ( MODE != "automatic" ) {
        input "Are you certain you want to =====>${OPERATION}<===== the =====>${CLUSTER_NAME}<===== cluster?"
    }

    try {
        cluster_detail = ""

        stage( 'Performance Test' ) {
            sshagent([CLUSTER_NAME]) {
                
                echo "Initial cluster state:"
                sh "ssh -o StrictHostKeyChecking=no opsmedic@use-tower2.ops.rhcloud.com status"
                echo "\n\n"

                sh "ssh -o StrictHostKeyChecking=no opsmedic@use-tower2.ops.rhcloud.com ${OPERATION}"
            }
        }

        if ( MODE != "silent" ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail_success(MAIL_LIST_SUCCESS)
        }

    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-cd@redhat.com",
                subject: "Error during ${OPERATION} on cluster ${CLUSTER_NAME}",
                body: """Encoutered an error: ${err}

Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
    }

}

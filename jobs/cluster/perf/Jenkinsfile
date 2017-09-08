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

@Library('aos_cd_ops') _

// Ask the shared library which clusters this job should act on
cluster_choice = aos_cd_ops_data.getClusterList("${env.BRANCH_NAME}").join("\n")  // Jenkins expects choice parameter to be linefeed delimited


node('openshift-build-1') {

    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jeder@redhat.com, vlaad@redhat.com, mifiedle@redhat.com, jupierce@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'mifiedle@redhat.com, jupierce@redhat.com, vlaad@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "${cluster_choice}", name: 'CLUSTER_SPEC', description: 'The name of the cluster specification to target'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "perf1\nperf2\nperf3", name: 'OPERATION', description: 'Test to perform'],
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "interactive\nquiet\nsilent\nautomatic", name: 'MODE', description: 'Select automatic to prevent input prompt. Select quiet to prevent aos-devel emails. Select silent to prevent any success email.'],
                              [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                      ]
             ]]
    )

    checkout scm

    def deploylib = load( "pipeline-scripts/deploylib.groovy")
    deploylib.initialize(CLUSTER_SPEC)

    currentBuild.displayName = "#${currentBuild.number} - ${OPERATION} ${CLUSTER_NAME}"


    if ( MODE != "automatic" ) {
        input "Are you certain you want to =====>${OPERATION}<===== the =====>${CLUSTER_NAME}<===== cluster?"
    }

    try {
        cluster_detail = ""

        sshagent([CLUSTER_ENV]) {

            stage( "pre-perf status" ) {
                echo "Cluster status BEFORE performance test:"
                deploylib.run("status")
            }

            stage("performance test"){
                deploylib.run(OPERATION)
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

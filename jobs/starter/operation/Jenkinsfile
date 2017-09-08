#!/usr/bin/env groovy

def mail_success(list) {
    mail(
        to: "${list}",
        from: "aos-cd@redhat.com",
        replyTo: 'jupierce@redhat.com',
        subject: "[aos-devel] Cluster ${OPERATION} complete: ${CLUSTER_NAME}",
        body: """\
Jenkins job: ${env.BUILD_URL}
""");
}

@Library('aos_cd_ops') _

// Ask the shared library which clusters this job should act on
cluster_choice = aos_cd_ops_data.getClusterList("${env.BRANCH_NAME}").join("\n")  // Jenkins expects choice parameter to be linefeed delimited

properties(
        [[$class              : 'ParametersDefinitionProperty',
          parameterDefinitions:
                  [
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com, mwoodson@redhat.com', description: 'Success for minor cluster operation', name: 'MAIL_LIST_SUCCESS'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com, mwoodson@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "${cluster_choice}", name: 'CLUSTER_SPEC', description: 'The specification of the cluster to affect'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "build-ci-msg\ncommit-config-loop\ndelete\ndisable-config-loop\ndisable-statuspage\ndisable-zabbix-maint\nenable-config-loop\nenable-statuspage\nenable-zabbix-maint\ngenerate-byo-inventory\ninstall\nlegacy-upgrade\nperf1\nperf2\nperf3\npre-check\nrun-config-loop\nsmoketest\nstatus\nupdate-inventory\nupdate-yum-extra-repos\nupgrade\nupgrade-control-plane\nupgrade-logging\nupgrade-metrics\nupgrade-nodes\n", name: 'OPERATION', description: 'Operation to perform'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "interactive\nquiet\nsilent\nautomatic", name: 'MODE', description: 'Select automatic to prevent input prompt. Select quiet to prevent aos-devel emails. Select silent to prevent any success email.'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                  ]
         ]]
)

node('openshift-build-1') {

    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode to pick up any new parameters" )
    }

    checkout scm

    def deploylib = load( "pipeline-scripts/deploylib.groovy")
    deploylib.initialize(CLUSTER_SPEC)

    currentBuild.displayName = "#${currentBuild.number} - ${OPERATION} ${CLUSTER_NAME}"

    if ( MODE != "automatic" ) {
        input "Are you certain you want to =====>${OPERATION}<===== the =====>${CLUSTER_NAME}<===== cluster?"
    }

    // Clusters that can be deleted & installed
    disposableCluster = [ 'test-key', 'cicd', 'free-int'].contains( CLUSTER_NAME )

    if (( OPERATION == "install" || OPERATION == "delete")  && !disposableCluster ) {
        error( "This script is not permitted to perform that operation" )
    }

    try {
        stage( 'operation' ) {
            sshagent([CLUSTER_ENV]) {
                if ( OPERATION == "reinstall" ) {
                    deploylib.run( "delete" )
                    deploylib.run( "install" )
                } else {
                    deploylib.run( OPERATION )
                }
            }
        }

        if ( MODE != "silent" ) {
            mail_success(MAIL_LIST_SUCCESS)
        }

    } catch ( err ) {
        mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-cd@redhat.com",
                subject: "Error during ${OPERATION} on cluster ${CLUSTER_NAME}",
                body: """Encountered an error: ${err}

Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
    }

}

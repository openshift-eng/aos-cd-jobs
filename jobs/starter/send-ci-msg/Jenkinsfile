#!/usr/bin/env groovy

@Library('aos_cd_ops') _

// Ask the shared library which clusters this job should act on
cluster_choice = aos_cd_ops_data.getClusterList("${env.BRANCH_NAME}").join("\n")  // Jenkins expects choice parameter to be linefeed delimited

properties(
        [[$class              : 'ParametersDefinitionProperty',
          parameterDefinitions:
                  [
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "${cluster_choice}", name: 'CLUSTER_SPEC', description: 'The cluster specification to inspect'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                  ]
         ]]
)


node('openshift-build-1') {

    checkout scm

    def deploylib = load( "pipeline-scripts/deploylib.groovy")
    deploylib.initialize(CLUSTER_SPEC)

    sshagent([CLUSTER_ENV]) {
        stage("send ci msg") {
            msg = deploylib.run("build-ci-msg", null, true, false)
            echo "Sending CI Message:\n${msg}"
            sendCIMessage messageContent: '',
                          messageProperties: msg,
                          messageType: 'ComponentBuildDone',
                          overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
                          providerName: 'Red Hat UMB'
        }
    }

}

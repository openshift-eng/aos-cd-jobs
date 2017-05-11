#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}



node('buildvm-devops') {

    // Expose properties for a parameterized build
    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'git@github.com:openshift/origin.git  git@github.com:openshift/origin-web-console.git git@github.com:openshift/ose.git git@github.com:openshift/openshift-ansible.git', description: 'Repositories to fork to stage', name: 'REPOS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Last sprint number (e.g. "130"); stage-### will be used to archive any previous stage branch', name: 'LAST_SPRINT_NUMBER'],
                      ]
             ]]
    )
    checkout scm
    
    set_workspace()

    if ( LAST_SPRINT_NUMBER == "" ) {
        error( "LAST_SPRINT_NUMBER is a required parameter" )
    }

    sshagent(['openshift-bot']) { // errata puddle must run with the permissions of openshift-bot to succeed
        sh "./scripts/stagecut.sh ${LAST_SPRINT_NUMBER} ${REPOS}"
    }

}

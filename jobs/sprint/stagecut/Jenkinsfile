#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}



node('openshift-build-1') {

    // Expose properties for a parameterized build
    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'git@github.com:openshift/origin.git  git@github.com:openshift/origin-web-console.git git@github.com:openshift/ose.git git@github.com:openshift/openshift-ansible.git', description: 'Repositories to fork to stage', name: 'REPOS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Non-default version source (e.g. 3.6) or blank for master branches', name: 'SOURCE_VERSION'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Last sprint number (e.g. "130"); stage-### will be used to archive any previous stage branch', name: 'LAST_SPRINT_NUMBER'],
                              [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Synch master to stage only (do not backup old stage branch)? Run only if stagecut is already in progress.', name: 'DESTRUCTIVE_SYNCH'],
                              [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Run in non-commit test?.', name: 'TEST_MODE'],
                              [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?.', name: 'MOCK'],
                      ]
             ]]
    )

    if ( MOCK.toBoolean() ) {
        error( "Ran in mock mode to pick up any new parameters" )
    }

    checkout scm
    
    set_workspace()

    if ( DESTRUCTIVE_SYNCH.toBoolean() ) {
        LAST_SPRINT_NUMBER = "na" // not applicable
    }
    
    if ( LAST_SPRINT_NUMBER == "" ) {
        error( "LAST_SPRINT_NUMBER is a required parameter" )
    }

    sshagent(['openshift-bot']) { // errata puddle must run with the permissions of openshift-bot to succeed
        env.TEST_MODE="${TEST_MODE}"
        env.SOURCE_VERSION="${SOURCE_VERSION}"
        env.DESTRUCTIVE_SYNCH = "${DESTRUCTIVE_SYNCH}"
        sh "./scripts/stagecut.sh ${LAST_SPRINT_NUMBER} ${REPOS}"
    }

}

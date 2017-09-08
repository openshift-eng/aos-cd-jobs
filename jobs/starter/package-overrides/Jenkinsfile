#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

node('openshift-build-1') {
    set_workspace()

    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.ChoiceParameterDefinition', choices: "online-int\nonline-stg\nonline-prod", name: 'REPO', description: 'The repository to populate'],
                              [$class: 'hudson.model.StringParameterDefinition', name: 'PACKAGES', description: 'Space delimited list of build NVRs (e.g. docker-1.12.6-30.git97ba2c0.el7). These builds will be pulled from brew and used to populate the specified repository.'],
                      ]
             ]]
    )

    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "REPO:[${REPO}], PACKAGES:[${PACKAGES}]"

    checkout scm

    withCredentials([[
            $class: 'FileBinding',
            credentialsId: 'ocp-build.keytab',
            variable: 'KEYTAB'
        ]]) {
        sh 'kinit -k -t $KEYTAB ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM'
    }

    // Run the script on rcm-guest in order to have the necessary privileges to push repos to mirrors.
    sh "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com sh -s ${REPO} ${PACKAGES} < ${env.WORKSPACE}/scripts/update-cluster-overrides.sh"

}

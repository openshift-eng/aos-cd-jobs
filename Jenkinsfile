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
            [
                    disableConcurrentBuilds(),
                    [$class: 'ParametersDefinitionProperty',
                     parameterDefinitions:
                             [
                                     [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-devel@redhat.com, aos-qe@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                                     [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,tdawson@redhat.com,smunilla@redhat.com,sedgar@redhat.com,vdinh@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                             ]
                    ],
                    [$class: 'PipelineTriggersJobProperty',
                     triggers: [[
                                        $class: 'TimerTrigger',
                                        spec  : 'H 11 * * *'
                                ]]
                    ]
            ]
    )
    
    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "onSuccess:[${MAIL_LIST_SUCCESS}], onFailure:[${MAIL_LIST_FAILURE}]"

    set_workspace()
    stage('Merge and build') {
        try {
            checkout scm
            sshagent(['openshift-bot']) { // merge-and-build must run with the permissions of openshift-bot to succeed
                sh "./scripts/merge-and-build-openshift-scripts.sh"
            }
        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    subject: "Error building openshift-scripts",
                    body: """Encoutered an error while running merge-and-build-openshift-scripts.sh: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        }

    }
}

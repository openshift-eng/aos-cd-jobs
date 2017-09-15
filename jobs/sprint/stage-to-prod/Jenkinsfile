#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

def version(f) {
    def matcher = readFile(f) =~ /Version:\s+([.0-9]+)/
    matcher ? matcher[0][1] : null
}

def mail_success() {
    mail(
        to: "${MAIL_LIST_SUCCESS}",
        from: "aos-cd@redhat.com",
        replyTo: 'smunilla@redhat.com',
        subject: "Stage has been synced to prod",
        body: """\
For details see the jenkins job.
Jenkins job: ${env.BUILD_URL}
""");
}

node('openshift-build-1') {

    // Expose properties for a parameterized build
    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                               [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Really sync Stage to Prod?', name: 'CONFIRM_STAGE_TO_PROD'],

                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,smunilla@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,smunilla@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                      ]
             ]]
    )
    
    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    echo "Confirm:${CONFIRM_STAGE_TO_PROD}, MAIL_LIST_SUCCESS:[${MAIL_LIST_SUCCESS}], MAIL_LIST_FAILURE:[${MAIL_LIST_FAILURE}]"

    set_workspace()
    stage('Stage to Prod') {
        try {
           
           if(CONFIRM_STAGE_TO_PROD == "true") {
               sshagent(['openshift-bot']) { // errata puddle must run with the permissions of openshift-bot to succeed
                    sh "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com /mnt/rcm-guest/puddles/RHAOS/scripts/mirrors-stage-to-prod.sh"
                }

                // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
                mail_success()
            }

        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "${MAIL_LIST_FAILURE}",
                    from: "aos-cd@redhat.com",
                    subject: "Error syncing stage to prod on mirrors",
                    body: """Encoutered an error while syncing stage to prod on mirrors: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        }

    }
}

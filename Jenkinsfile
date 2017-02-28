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

def mail_success(version) {
    mail(
        to: "${MAIL_LIST_SUCCESS}",
        replyTo: 'tdawson@redhat.com',
        subject: "[aos-devel] New AtomicOpenShift Puddle for OSE: ${version}",
        body: """\
v${version}
Images have been built for this puddle
Images have been pushed to registry.ops
Puddles have been synched to mirrors
Jenkins job: ${env.BUILD_URL}
""");
}

node('buildvm-devops') {

    // Expose properties for a parameterized build
    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Major Version', name: 'OSE_MAJOR'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Minor Version', name: 'OSE_MINOR'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-devel@redhat.com, aos-qe@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,tdawson@redhat.com,smunilla@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                      ]
             ]]
    )
    
    // Force Jenkins to fail early if this is the first time this job has been run/and or new parameters have not been discovered.
    // echo "${OSE_MAJOR}.${OSE_MINOR}, onSuccess:[${MAIL_LIST_SUCCESS}], onFailure:[${MAIL_LIST_FAILURE}]"

    set_workspace()
    stage('Merge and build') {
        try {
            checkout scm
            sh "./scripts/merge-and-build.sh ${OSE_MAJOR} ${OSE_MINOR}"

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            // mail_success(version("go/src/github.com/openshift/ose/origin.spec"))


        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            //  mail(to: "${MAIL_LIST_FAILURE}",
            //        subject: "Error building OSE: ${OSE_MAJOR}.${OSE_MINOR}",
            //       body: """Encoutered an error while running merge-and-build.sh: ${err}
            //Jenkins job: ${env.BUILD_URL}
            //""");

            // Re-throw the error in order to fail the job
            throw err
        }

    }
}

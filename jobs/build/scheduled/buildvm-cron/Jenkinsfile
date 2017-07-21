
// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

node('openshift-build-1') {

    // Expose properties for a parameterized build
    properties(
            [
                    disableConcurrentBuilds(),
                    [$class: 'PipelineTriggersJobProperty',
                     triggers: [[
                                        $class: 'TimerTrigger',
                                        spec  : '5 0 * * *'
                                ]]
                    ]
            ]
    )
    
    checkout scm
    env.PATH = "${pwd()}/build-scripts/ose_images:${env.PATH}"    

    set_workspace()
    stage('Maintenance') {
        try {
            checkout scm
            sh "./scripts/maintenance.sh"
        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "jupierce@redhat.com,smunilla@redhat.com",
                    from: "aos-cd@redhat.com",
                    subject: "Error running buildvm maintenance",
                    body: """${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        }

    }
}

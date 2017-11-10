

properties(
        [
                buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '360')),
                [$class : 'ParametersDefinitionProperty',
                 parameterDefinitions:
                         [
                                 [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                         ]
                ],
                disableConcurrentBuilds()
        ]
)

node('openshift-build-1') {

    checkout scm

    def commonlib = load( "pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    try {
        buildlib = load('pipeline-scripts/buildlib.groovy')
        buildlib.initialize()

        sshagent(["openshift-bot"]) {

            // Capture exceptions and don't let one problem stop other cleanup from executing
            e1 = null
            e2 = null

            try {
                stage("oit setup"){
                    sh 'rm -rf enterprise-images'
                    sh 'git clone git@github.com:openshift/enterprise-images.git'
                }

                stage("push images") {
                    dir ( "enterprise-images" ) {
                        sh './oit/oit.py --user=ocp-build --group sync-misc distgits:push-images --to-defaults'
                        sh './oit/oit.py --user=ocp-build --group sync-3.7 distgits:push-images --to-defaults'
                        try {
                            sh './oit/oit.py --user=ocp-build --group sync-3.8 distgits:push-images --to-defaults'
                        } catch ( e38 ) {
                            // need dist-git branches before this will work without exceptions; swallow for now
                        }
                    }
                }
            } catch ( ex1 ) {
                e1 = ex1
            }

            try {
                stage("legacy maint") {
                    sh "./scripts/maintenance.sh"
                }
            } catch ( ex2 ) {
                e2 = ex2
            }

            if ( e1 != null ) {
                throw e1
            }

            if ( e2 != null ) {
                throw e2
            }

        }

    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "jupierce@redhat.com",
                from: "aos-cd@redhat.com",
                subject: "Error running buildvm maintenance",
                body: """${err}


Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }

}

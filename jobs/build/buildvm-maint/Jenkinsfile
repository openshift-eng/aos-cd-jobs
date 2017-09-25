

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

        sshagent(["openshift-bot"]) {
            stage("oit setup"){

                sh 'rm -rf enterprise-images'

                git 'https://github.com/openshift/enterprise-images.git'

                dir ( "enterprise-images" ) {
                    sh 'virtualenv env'
                    sh 'env/bin/pip install -r oit/oit/requirements.txt'
                }

            }

            stage("push images") {
                dir ( "enterprise-images" ) {
                    buildlib.with_virtualenv("${pwd()}/env") {
                        sh './oit --user=ocp-build --group sync-3.6 distgits:push-images --to-defaults'
                    }
                }
            }

            stage("legacy maint") {
                // sh "./scripts/maintenance.sh"
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



properties(
    [
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '',
                artifactNumToKeepStr: '',
                daysToKeepStr: '',
                numToKeepStr: '360'
            )
        ),
        [
            $class : 'ParametersDefinitionProperty',
            parameterDefinitions: [
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false,
                ],
            ]
        ],
        disableConcurrentBuilds()
    ]
)

node('openshift-build-1') {

    checkout scm

    def commonlib = load( "pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    def buildlib = load( "pipeline-scripts/buildlib.groovy" )
    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def doozer_working = "${WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(doozer_working)

    try {
        buildlib = load('pipeline-scripts/buildlib.groovy')
        buildlib.initialize()

        sshagent(["openshift-bot"]) {

            // Capture exceptions and don't let one problem stop other cleanup from executing
            e1 = null
            e2 = null
            e3 = null

            try {
                stage("push images") {
                    dir ( "enterprise-images" ) {
                        sh 'doozer --working-dir ${doozer_working} --group sync-3.9 images:push --to-defaults'
                        buildlib.cleanWorkdir(doozer_working)
                        sh 'doozer --working-dir ${doozer_working} --group sync-misc images:push --to-defaults'
                        buildlib.cleanWorkdir(doozer_working)
                        sh 'doozer --working-dir ${doozer_working} --group sync-3.7 images:push --to-defaults'
                        buildlib.cleanWorkdir(doozer_working)
                    }
                }
            } catch ( ex1 ) {
                echo "ERROR: ex1 occurred: " + ex1
                e1 = ex1
            }

            try {
                stage("legacy maint") {
                    withEnv(["PATH=${env.PATH}:${pwd()}/build-scripts/ose_images"]) {
                        sh "./scripts/maintenance.sh"
                    }
                }
            } catch ( ex2 ) {
                echo "ERROR: ex2 occurred: " + ex2
                e2 = ex2
            }

            try {
                stage("snapshot system setup") {
                    snapshot_diff = sh(returnStdout: true, script: "./scripts/snapshot.sh /home/jenkins").trim()
                    if ( snapshot_diff != "") {
                      def snapshot = readFile("/home/jenkins/new_snapshot.txt")
                      mail(to: "jupierce@redhat.com,ahaile@redhat.com,smunilla@redhat.com",
                              from: "aos-cicd@redhat.com",
                              subject: "BuildVM Snapshot",
                              body: "${snapshot}");
                    }
                }
            } catch ( ex3 ) {
                echo "ERROR: ex3 occurred: " + ex3
                e3 = ex3
            }

            if ( e1 != null ) {
                throw e1
            }

            if ( e2 != null ) {
                throw e2
            }

            if ( e3 != null ) {
                throw e3
            }

        }

    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "jupierce@redhat.com,tbielawa@redhat.com",
                from: "aos-cicd@redhat.com",
                subject: "Error running buildvm maintenance",
                body: """${err}


Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }

}

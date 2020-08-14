

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
        disableResume(),
        disableConcurrentBuilds()
    ]
)

node('openshift-build-1') {

    checkout scm

    def buildlib = load( "pipeline-scripts/buildlib.groovy" )
    buildlib.initialize()
    def commonlib = buildlib.commonlib
    commonlib.describeJob("buildvm-maint", """
        -------------------------------------------
        Ancient "maintenance" job for odds and ends
        -------------------------------------------
        Timing: The scheduled job of the same name runs this daily.

        Several assorted functions, including:
        * Mirroring various custom sets of content (ocp-build-data#sync-FOO branches) for SD ops.
        * Cleaning out old docker images and tito files.

        It's not clear anyone remembers what all this actually does or whether we could just disable it.
        If you figure it out, update this or get rid of the job as appropriate.
    """)

    // doozer_working must be in WORKSPACE in order to have artifacts archived
    def doozer_working = "${WORKSPACE}/doozer_working"
    buildlib.cleanWorkdir(doozer_working)

    try {
        sshagent(["openshift-bot"]) {

            // Capture exceptions and don't let one problem stop other cleanup from executing
            errors = []

            try {
                stage("push images") {
                    dir ( "enterprise-images" ) {
                        sh "doozer --working-dir ${doozer_working} --group sync-3.9 images:push --to-defaults"
                        buildlib.cleanWorkdir(doozer_working)
                        sh "doozer --working-dir ${doozer_working} --group sync-misc images:push --to-defaults"
                        buildlib.cleanWorkdir(doozer_working)
                        sh "doozer --working-dir ${doozer_working} --group sync-3.7 images:push --to-defaults"
                        buildlib.cleanWorkdir(doozer_working)
                    }
                }
            } catch ( ex1 ) {
                echo "ERROR: ex1 occurred: " + ex1
                errors[1] = ex1
            }

            try {
                stage("legacy maint") {
                    withEnv(["PATH=${env.PATH}:${pwd()}/build-scripts/ose_images"]) {
                        sh "./scripts/maintenance.sh"
                    }
                }
            } catch ( ex2 ) {
                echo "ERROR: ex2 occurred: " + ex2
                errors[2] = ex2
            }

            try {
                stage("snapshot system setup") {
                    snapshot_diff = sh(returnStdout: true, script: "./scripts/snapshot.sh /home/jenkins").trim()
                    if ( snapshot_diff != "") {
                        // Want to see what's in the snapshots directory?
                        //   $ rclone tree s3SigningLogs:art-build-artifacts/buildvm-snapshots/
                        try {
                            sh("/bin/rclone -v copyto /home/jenkins/new_snapshot.txt s3SigningLogs:art-build-artifacts/buildvm-snapshots/`date '+%Y%m%d'`.txt")
                        } catch ( snapErr ) {
                            errors[4] = snapErr
                            def snapshot = readFile("/home/jenkins/new_snapshot.txt")
                            mail(to: "aos-art-automation+new-buildvm-snapshot@redhat.com",
                                 from: "aos-art-automation@redhat.com",
                                 replyTo: 'aos-team-art@redhat.com',
                                 subject: "BuildVM Snapshot",
                                 body: "${snapshot}");
                        }
                    }
                }
            } catch ( ex3 ) {
                echo "ERROR: ex3 occurred: " + ex3
                errors[3] = ex3
            }

            errors.each {
                if (it != null) {
                    throw it
                }
            }
        }

    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "aos-art-automation+failed-buildvm-maintenance@redhat.com",
             from: "aos-art-automation@redhat.com",
	     replyTo: "aos-team-art@redhat.com",
             subject: "Error running buildvm maintenance",
             body: """${err}


Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }

}

node('buildvm-devops') {

    // Expose properties for a parameterized build
    properties(
            [[$class              : 'ParametersDefinitionProperty',
              parameterDefinitions:
                      [
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Major Version', name: 'OSE_MAJOR'],
                              [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'OSE Minor Version', name: 'OSE_MINOR'],
                      ]
             ]]
    )

    stage('Merge and build') {
        try {
            checkout scm
            sh "./merge-build-push/merge-and-build.sh ${OSE_MAJOR} ${OSE_MINOR}"

            def specVersion = readFile( file: 'go/src/github.com/openshift/ose/origin.spec' ).find( /Version: ([.0-9]+)/) {
                full, ver -> return ver;
            }

            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "jupierce@redhat.com",
                    subject: "[aos-devel] New AtomicOpenShift Puddle for OSE: ${specVersion}",
                    body: """v${specVersion}
Images have been built for this puddle
Images have been pushed to registry.ops
Puddles have been synched to mirrors


Jenkins job: ${env.BUILD_URL}
""");


        } catch ( err ) {
            // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
            mail(to: "jupierce@redhat.com",
                    subject: "Error building OSE: ${OSE_MAJOR}.${OSE_MINOR}",
                    body: """Encoutered an error while running merge-and-build.sh: ${err}


Jenkins job: ${env.BUILD_URL}
""");
            // Re-throw the error in order to fail the job
            throw err
        }

    }
}

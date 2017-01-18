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
        // sh "./merge-and-build.sh --major=${OSE_MAJOR} --minor=${OSE_MINOR}"

        /*
        def specVersion = readFile( file: 'ose/origin.spec' ).find( /Version: ([.0-9]+)/) {
            full, ver -> return ver;
        }*/
        def specVersion="3.5.0.5"

        mail(to: "jupierce@redhat.com",
                subject: "[aos-devel] New AtomicOpenShift Puddle for: ${specVersion}",
                body: """v${specVersion}
Images have been built for this puddle
Images have been pushed to registry.ops
Puddles have been synched to mirrors


Jenkins job: ${env.BUILD_URL}
""");

    }
}

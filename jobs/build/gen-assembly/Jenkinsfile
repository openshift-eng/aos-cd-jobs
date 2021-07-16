
node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("gen-assembly", """
            <h2>Generate a recommended definition for an assembly based on a set of nightlies</h2>
            This are no side effects from running this job. It is the responsibility of the Artist
            to check the results into git / releases.yml.
        """)

        properties(
            [
                disableResume(),
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: "50",
                        daysToKeepStr: "50"
                        )),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.doozerParam(),
                        commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                        string(
                            name: "ASSEMBLY_NAME",
                            description: "The name of the proposed assembly (e.g. 4.9.12 or art1234)",
                            trim: true
                        ),
                        string(
                            name: "NIGHTLIES",
                            description: "List of nightlies for each arch, separated by comma. For custom releases you do not need a nightly for each arch.",
                            trim: true
                        ),
                        booleanParam(
                            name: 'CUSTOM',
                            description: 'Custom assemblies are not for official release. They can, for example, not have all required arches for the group.',
                            defaultValue: false,
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()
        stage("initialize") {
            buildlib.initialize()
            buildlib.registry_quay_dev_login()
            currentBuild.displayName += " - ${BUILD_VERSION} - ${ASSEMBLY_NAME}"
        }

        stage("gen-assembly") {
            withEnv(['KUBECONFIG=/home/jenkins/kubeconfigs/art-publish.app.ci.kubeconfig']) {
                nightly_args = ""
                for (nightly in params.NIGHTLIES.split(',')) {
                    nightly_args += " --nightly ${nightly.trim()}"
                }
                cmd = "--group openshift-${BUILD_VERSION} release:gen-assembly --name ${ASSEMBLY_NAME} from-nightlies ${nightly_args}"
                if (params.CUSTOM) {
                    cmd += ' --custom'
                }
                buildlib.doozer(cmd)
            }
        }

        buildlib.cleanWorkspace()
    }
}

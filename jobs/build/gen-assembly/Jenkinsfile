
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
                            description: "List of nightlies for each arch. For custom releases you do not need a nightly for each arch.",
                            trim: true
                        ),
                        booleanParam(
                            name: 'CUSTOM',
                            description: 'Custom assemblies are not for official release. They can, for example, not have all required arches for the group.',
                            defaultValue: false,
                        ),
                        string(
                            name: 'IN_FLIGHT_PREV',
                            description: 'This is the in-flight release version of previous minor version of OCP. If there is no in-flight release, use "none".',
                            defaultValue: "",
                            trim: true,
                        ),
                        string(
                            name: 'PREVIOUS',
                            description: '[Optional] Leave empty to use suggested previous. Otherwise, follow item #6 "PREVIOUS" of the following doc for instructions on how to fill this field:\nhttps://mojo.redhat.com/docs/DOC-1201843#jive_content_id_Completing_a_4yz_release',
                            defaultValue: "",
                            trim: true,
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
            if (!params.IN_FLIGHT_PREV) {
                error('IN_FLIGHT_PREV is required. If there is no in-flight release, use "none".')
            }
        }

        stage("gen-assembly") {
            withEnv(['KUBECONFIG=/home/jenkins/kubeconfigs/art-publish.app.ci.kubeconfig']) {
                nightly_args = ""
                for (nightly in commonlib.parseList(params.NIGHTLIES)) {
                    nightly_args += " --nightly ${nightly.trim()}"
                }
                cmd = "--group openshift-${BUILD_VERSION} release:gen-assembly --name ${ASSEMBLY_NAME} from-releases ${nightly_args}"
                if (params.CUSTOM) {
                    cmd += ' --custom'
                    if ((params.IN_FLIGHT_PREV && params.IN_FLIGHT_PREV != 'none') || params.PREVIOUS) {
                        error("Specifying IN_FLIGHT_PREV or PREVIOUS for a custom release is not allowed.")
                    }
                }
                else {
                    if (params.IN_FLIGHT_PREV && params.IN_FLIGHT_PREV != 'none') {
                        cmd += " --in-flight ${IN_FLIGHT_PREV}"
                    }
                    if (params.PREVIOUS) {
                        for (previous in params.PREVIOUS.split(',')) {
                            cmd += " --previous ${previous.trim()}"
                        }
                    } else {
                        cmd += ' --auto-previous'
                    }
                }
                buildlib.doozer(cmd)
            }
        }

        buildlib.cleanWorkspace()
    }
}

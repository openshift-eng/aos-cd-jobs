
node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("gen-assembly", """
            <h2>Generate a recommended definition for an assembly based on a set of nightlies</h2>
            Find nightlies ready for release and define an assembly to add to <code>releases.yml</code>.
            See <code>doozer get-nightlies -h</code> to learn how nightlies are found.
            This are no side effects from running this job. It is the responsibility of the ARTist
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
                            name: 'DOOZER_DATA_PATH',
                            description: 'ocp-build-data fork to use (e.g. assembly definition in your own fork)',
                            defaultValue: "https://github.com/openshift/ocp-build-data",
                            trim: true,
                        ),
                        string(
                            name: "NIGHTLIES",
                            description: "(Optional) List of nightlies to match with <code>doozer get-nightlies</code> (if empty, find latest)",
                        ),
                        booleanParam(
                            name: 'ALLOW_PENDING',
                            description: 'Match nightlies that have not completed tests',
                            defaultValue: false,
                        ),
                        booleanParam(
                            name: 'ALLOW_REJECTED',
                            description: 'Match nightlies that have failed their tests',
                            defaultValue: false,
                        ),
                        booleanParam(
                            name: 'ALLOW_INCONSISTENCY',
                            description: 'Allow matching nightlies built from matching commits but with inconsistent RPMs',
                            defaultValue: false,
                        ),
                        booleanParam(
                            name: 'CUSTOM',
                            description: 'Custom assemblies are not for official release. They can, for example, not have all required arches for the group.',
                            defaultValue: false,
                        ),
                        string(
                            name: 'LIMIT_ARCHES',
                            description: '(Optional) (for custom assemblies only) Limit included arches to this list',
                            defaultValue: "",
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
            currentBuild.displayName += " - ${params.BUILD_VERSION} - ${params.ASSEMBLY_NAME}"
            if (!params.IN_FLIGHT_PREV) {
                error('IN_FLIGHT_PREV is required. If there is no in-flight release, use "none".')
            }
            doozerParams = "--group openshift-${params.BUILD_VERSION} --data-path ${params.DOOZER_DATA_PATH}"
            if (params.LIMIT_ARCHES.trim()) {
                if (!params.CUSTOM) error('LIMIT_ARCHES can only be used with custom assemblies.')
                doozerParams += " --arches ${commonlib.cleanCommaList(params.LIMIT_ARCHES)}"
            }
        }

        stage("get-nightlies") {
            def nightly_args = ""
            if (params.ALLOW_PENDING) nightly_args += "--allow-pending"
            if (params.ALLOW_REJECTED) nightly_args += " --allow-rejected"
            if (params.ALLOW_INCONSISTENCY) nightly_args += " --allow-inconsistency"
            for (nightly in commonlib.parseList(params.NIGHTLIES)) {
                nightly_args += " --matching ${nightly.trim()}"
            }
            cmd = "${doozerParams} get-nightlies ${nightly_args}"
            nightlies = commonlib.parseList(buildlib.doozer(cmd, [capture: true]))
        }
        stage("gen-assembly") {
            withEnv(['KUBECONFIG=/home/jenkins/kubeconfigs/art-publish.app.ci.kubeconfig']) {
                nightly_args = ""
                for (nightly in nightlies) {
                    nightly_args += " --nightly ${nightly.trim()}"
                }
                cmd = "${doozerParams} release:gen-assembly --name ${params.ASSEMBLY_NAME} from-releases ${nightly_args}"
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
                        if (params.PREVIOUS != 'none') {
                            for (previous in params.PREVIOUS.split(',')) {
                                cmd += " --previous ${previous.trim()}"
                            }
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


node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("gen-assembly", """
            <h2>Generate a recommended definition for an assembly based on a set of nightlies</h2>
            Find nightlies ready for release and define an assembly to add to <code>releases.yml</code>.
            See <code>doozer get-nightlies -h</code> to learn how nightlies are found.
            A pull request will be automatically created to add the generated assembly definition to releases.yml.
            It is the responsibility of the ARTist to review and merge the PR.
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
                        commonlib.artToolsParam(),
                        commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                        string(
                            name: "ASSEMBLY_NAME",
                            description: "The name of the proposed assembly (e.g. 4.9.12, ec.0, or art1234)",
                            trim: true
                        ),
                        string(
                            name: 'DOOZER_DATA_PATH',
                            description: 'ocp-build-data fork to use (e.g. assembly definition in your own fork)',
                            defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                            trim: true,
                        ),
                        string(
                            name: "NIGHTLIES",
                            description: "(Optional for public nightlies) List of nightlies to match with <code>doozer get-nightlies</code> (if empty, find latest). If preparing from private nightlies, provide the amd64 nightly as parameter, to match. The automation will find the corresponding nightlies for other arches.",
                            trim: true,
                        ),
                        choice(
                            name: 'BUILD_SYSTEM',
                            description: 'Whether we should look at Brew or Konflux builds',
                            choices: ['brew', 'konflux'].join('\n'),
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
                            name: 'GEN_MICROSHIFT',
                            description: 'Create microshift entry for named release based on request',
                            defaultValue: false,
                        ),
                        booleanParam(
                            name: 'IGNORE_NON_X86',
                            description: 'When non x86_64 arch are inconsistent with x86_64 nightly, ignore them and only honor the x86_64 nightly',
                            defaultValue: false,
                        ),
                        booleanParam(
                            name: 'ALLOW_INCONSISTENCY',
                            description: 'Allow matching nightlies built from matching commits but with inconsistent RPMs',
                            defaultValue: false,
                        ),
                        choice(
                            name: 'PRE_GA_MODE',
                            description: 'Prepare the advisory for "prerelease" operator release',
                            choices: ["none", "prerelease"].join("\n"),
                        ),
                        booleanParam(
                            name: 'CUSTOM',
                            description: 'Custom assemblies are not for official release. They can, for example, not have all required arches for the group.',
                            defaultValue: false,
                        ),
                        string(
                            name: 'LIMIT_ARCHES',
                            description: '(Optional) Limit included arches to this list. Valid values are (aarch64, ppc64le, s390x, x86_64)',
                            defaultValue: "",
                            trim: true,
                        ),
                        string(
                            name: 'IN_FLIGHT_PREV',
                            description: '[Optional] Leave empty to use auto-fetched in-flight version. This is the in-flight release version of previous minor version of OCP. If there is no in-flight release, use "none".',
                            defaultValue: "",
                            trim: true,
                        ),
                        string(
                            name: 'PREVIOUS',
                            description: '[Optional] Leave empty to use suggested previous. "none" for no previous. Otherwise, follow item #6 "PREVIOUS" of the following doc for instructions on how to fill this field:\nhttps://mojo.redhat.com/docs/DOC-1201843#jive_content_id_Completing_a_4yz_release',
                            defaultValue: "",
                            trim: true,
                        ),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: false
                        ),
                        booleanParam(
                            name: "TRIGGER_BUILD_SYNC",
                            description: "Automatically trigger build sync against the automatically created PR",
                            defaultValue: true
                        ),
                        booleanParam(
                            name: "SKIP_GET_NIGHTLIES",
                            description: "Skip checking for consistent nightlies and proceed with the ones provided in the NIGHTLIES parameter",
                            defaultValue: false
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()
        stage("initialize") {
            buildlib.registry_quay_dev_login()
            currentBuild.displayName += " - ${params.BUILD_VERSION} - ${params.ASSEMBLY_NAME}"
            if (!params.ASSEMBLY_NAME) {
                error('ASSEMBLY_NAME is required.')
            }
        }

        stage("gen-assembly") {
            buildlib.cleanWorkdir("./artcd_working")
            sh "mkdir -p ./artcd_working"
            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config", "./config/artcd.toml",
            ]

            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            cmd += [
                "gen-assembly",
                "--data-path", params.DOOZER_DATA_PATH,
                "--build-system", params.BUILD_SYSTEM,
                "-g", "openshift-$params.BUILD_VERSION",
                "--assembly", params.ASSEMBLY_NAME,
            ]
            if (params.LIMIT_ARCHES) {
                for (arch in params.LIMIT_ARCHES.split("[,\\s]+")) {
                    cmd << "--arch" << arch.trim()
                }
            }
            if (params.NIGHTLIES) {
                for (nightly in params.NIGHTLIES.split("[,\\s]+")) {
                    cmd << "--nightly" << nightly.trim()
                }
            }
            if (params.ALLOW_PENDING) {
                cmd << "--allow-pending"
            }
            if (params.ALLOW_REJECTED) {
                cmd << "--allow-rejected"
            }
            if (params.GEN_MICROSHIFT) {
                cmd << "--gen-microshift"
            }
            if (params.IGNORE_NON_X86) {
                cmd << "--ignore-non-x86-nightlies"
            }
            if (params.ALLOW_INCONSISTENCY) {
                cmd << "--allow-inconsistency"
            }
            if (params.PRE_GA_MODE && params.PRE_GA_MODE != "none") {
                cmd << "--pre-ga-mode=${params.PRE_GA_MODE}"
            }
            if (params.CUSTOM) {
                cmd << "--custom"
            }
            if (params.IN_FLIGHT_PREV && params.IN_FLIGHT_PREV != "none") {
                cmd << "--in-flight=${params.IN_FLIGHT_PREV}"
            }
            if (params.PREVIOUS) {
                if (params.PREVIOUS != 'none') {
                    for (previous in params.PREVIOUS.split("[,\\s]+")) {
                        cmd << "--previous" << previous.trim()
                    }
                }
            } else {
                cmd << "--auto-previous"
            }
            if (params.TRIGGER_BUILD_SYNC) {
                cmd << "--auto-trigger-build-sync"
            }
            if (params.SKIP_GET_NIGHTLIES) {
                cmd << "--skip-get-nightlies"
            }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                    string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                    string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                    string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                ]) {
                    withEnv(["BUILD_URL=${BUILD_URL}"]) {
                        try {
                            commonlib.shell(script: cmd.join(' '))
                        } catch (err) {
                            throw err
                        } finally {
                            commonlib.safeArchiveArtifacts([
                                "artcd_working/**/*.log",
                            ])
                        }
                    }
                }
            }
        }
    }
}

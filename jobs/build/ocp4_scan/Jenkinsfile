node('covscan') {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("ocp4_scan", """
        <h2>Kick off incremental builds where needed</h2>
        This job scans OCP4 versions for any changes in sources, buildroots,
        etc. and schedules an incremental build if there are any.

        <b>Timing</b>: Run by the scheduled job of the same name, as often as possible
        (which is no more than hourly or so - depending on what has changed).

        <h1>DO NOT RUN THIS MANUALLY *</h1>
        * Humans MAY run this, but be aware that this will cause builds to run
        without respecting freeze_automation. If you just need to test something,
        limit it to a release that's not frozen.
    """)


    def doozer_working = "${WORKSPACE}/doozer_working"

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '7',
                    daysToKeepStr: '7'
                )
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    string(
                        name: 'VERSIONS',
                        description: '<a href="https://github.com/openshift/aos-cd-jobs/tree/master/jobs#list-parameters">List</a> of versions to scan.',
                        defaultValue: commonlib.ocp4Versions.join(','),
                        trim: true,
                    ),
                    booleanParam(
                        name: 'CLEAN_CLONE',
                        defaultValue: false,
                        description: 'Force all git repos to be re-pulled',
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-ocp4-scan@redhat.com',
                        ].join(','),
                        trim: true,
                    ),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    buildlib.initialize()

    versions = commonlib.parseList(params.VERSIONS)

    currentBuild.displayName = "#${currentBuild.number} Scanning versions ${params.VERSIONS}"
    currentBuild.description = ""

    try {
        successful = []
        sshagent(["openshift-bot"]) {
            stage("Scan") {
                for(version in versions) {
                    try {

                        if (!version.startsWith('4.')) {
                            error("This job is only intended for 4.y releases, not '${version}'.")
                        }

                        // this lock ensures we are not scanning during an active build
                        activityLockName = "github-activity-lock-${version}"

                        if (!buildlib.isBuildPermitted("--group 'openshift-${version}'")) {
                            echo "Builds are not currently permitted for ${version} -- skipping"
                            continue
                        }

                        // Check versions.size because if the user requested a specific version,
                        // they will expect it to happen, even if they need to wait.
                        if (versions.size() != 1 && !commonlib.canLock(activityLockName)) {
                            echo "Looks like there is another build ongoing for ${version} -- skipping for this run"
                            continue
                        }

                        // There is a vanishingly small race condition here, but it is not dangerous;
                        // it can only lead to undesired delays (i.e. waiting to scan while a build is ongoing).
                        lock(activityLockName) {

                            buildlib.cleanWorkdir(doozer_working, true)

                            def yamlStr = buildlib.doozer(
                                """
                                --working-dir ${doozer_working}
                                --group 'openshift-${version}'
                                config:scan-sources --yaml
                                --ci-kubeconfig ${buildlib.ciKubeconfig}
                                """, [capture: true]
                            )

                            echo "scan-sources output for openshift-${version}:\n${yamlStr}\n\n"

                            def yamlData = readYaml text: yamlStr

                            sh "mv ${doozer_working}/debug.log ${doozer_working}/debug-${version}.log"
                            sh "bzip2 ${doozer_working}/debug-${version}.log"
                            commonlib.safeArchiveArtifacts(["doozer_working/*.bz2"])

                            def rhcosChanged = false
                            for (stream in yamlData.get('rhcos', [])) {
                                if (stream['changed']) {
                                    echo "Detected at least one updated RHCOS."
                                    rhcosChanged = true
                                    break
                                }
                            }

                            def changed = buildlib.getChanges(yamlData)
                            if ( changed.rpms || changed.images ) {
                                echo "Detected source changes: ${changed}"
                                build(
                                    job: 'build%2Focp4',
                                    propagate: false,
                                    wait: false,
                                    parameters: [
                                        string(name: 'BUILD_VERSION', value: version),
                                        booleanParam(name: 'FORCE_BUILD', value: false),
                                    ]
                                )
                                currentBuild.description += "<br>triggered build: ${version}"
                            } else if (rhcosChanged) {
                                build(
                                    job: 'build%2Fbuild-sync',
                                    propagate: false,
                                    wait: false,
                                    parameters: [
                                        string(name: 'BUILD_VERSION', value: version),
                                    ]
                                )
                                currentBuild.description += "<br>triggered build-sync: ${version}"
                            }
                        }
                    } catch (err) {
                        currentBuild.result = "UNSTABLE"
                        currentBuild.description += """<p style="color:#d00">failed to scan ${version}</p>"""
                        echo "Error running ${version} scan:\n${err}"

                        commonlib.email(
                            to: "${params.MAIL_LIST_FAILURE}",
                            from: "aos-art-automation@redhat.com",
                            replyTo: "aos-team-art@redhat.com",
                            subject: "Error scanning OCP v${version}",
                            body: "Encountered an error while running OCP4 scan:\n${env.BUILD_URL}\n\n${err}"
                        )
                    }
                }
            }
        }

        if (params.MAIL_LIST_SUCCESS.trim()) {
            // success email only if requested for this build
            commonlib.email(
                to: "${params.MAIL_LIST_SUCCESS}",
                from: "aos-art-automation@redhat.com",
                replyTo: "aos-team-art@redhat.com",
                subject: "Success scanning OCP versions: ${versions.join(', ')}",
                body: "Success scanning OCP:\n${env.BUILD_URL}"
            )
        }

    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Unexpected error during OCP scan!",
            body: "Encountered an unexpected error while running OCP scan: ${err}"
        )

        throw err
    }
}

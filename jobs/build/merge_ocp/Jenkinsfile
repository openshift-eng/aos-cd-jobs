node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'VERSIONS',
                        description: 'CSV list of versions to run merge on.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: commonlib.ocpMergeVersions.join(',')
                    ],
                    booleanParam(
                        name: 'CLEAN_CLONE',
                        defaultValue: false,
                        description: 'Force all git repos to be re-pulled'
                    ),
                    booleanParam(
                        name: 'SCHEDULE_INCREMENTAL',
                        defaultValue: true,
                        description: 'If changes are detected, schedule an incremental build (4.x only)'
                    ),
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-ocp-merge@redhat.com',
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()

    mergeVersions = params.VERSIONS.split(',')
    mergeWorking = "${env.WORKSPACE}/ose"
    upstreamRemote = "git@github.com:openshift/origin.git"
    downstreamRemote = "git@github.com:openshift/ose.git"

    currentBuild.displayName = "#${currentBuild.number} Merging versions ${params.VERSIONS}"
    currentBuild.description = ""

    try {
        successful = []
        sshagent(["openshift-bot"]) {
            stage("Clone ose") {

                if ( params.CLEAN_CLONE ) {
                    sh "rm -rf ${mergeWorking}"
                }

                sh """
                set -exuo pipefail

                function reset_repo {
                    cd "${env.WORKSPACE}"
                    rm -rf ${mergeWorking}
                    git clone ${downstreamRemote} ${mergeWorking}
                    cd "${mergeWorking}"
                    git remote add upstream ${upstreamRemote}
                }


                if [[ ! -d "${mergeWorking}/.git" ]]; then
                    echo "invalid cached repo; resetting"
                    reset_repo
                    exit 0
                fi

                cd "${mergeWorking}"

                echo "Pre-reset status"
                git status
                git remote -v

                echo "Checking and resetting if necessary..."
                # Check for anything fishy in the clone state. Reset if anything found.

                if [[ `git remote get-url origin` != "${downstreamRemote}" ]]; then
                    echo "origin repo has changed; resetting"
                    reset_repo
                    exit 0
                fi

                if [[ `git remote get-url upstream` != "${upstreamRemote}" ]]; then
                    echo "upstream repo has changed; resetting"
                    reset_repo
                    exit 0
                fi

                if ! ( git fetch origin && git fetch upstream ) ; then
                    echo "Error fetching origin or upstream; resetting"
                    reset_repo
                    exit 0
                fi

                git reset --hard HEAD
                git clean -f -d
                git checkout master
                git reset --hard origin/master
                git pull
                """

            }

            stage("Merge") {
                for(int i = 0; i < mergeVersions.size(); ++i) {
                    def version = mergeVersions[i]
                    try {

                        // this lock ensures we are not merging during an active build
                        activityLockName = "github-activity-lock-${version}"

                        if (!buildlib.isBuildPermitted("--group 'openshift-${version}'")) {
                            echo "Builds are not currently permitted for ${version} -- skipping"
                            continue
                        }

                        // Check mergeVersions.size because, if the user requested a specific version
                        // they will expect it to happen, even if they need to wait
                        if (mergeVersions.size() == 1 || commonlib.canLock(activityLockName)) {

                            // There is a vanishingly small race condition here, but it is not dangerous;
                            // it can only lead to undesired delays (i.e. waiting to merge while a build is ongoing).
                            lock(activityLockName) {

                                def scheduleBuild = false

                                if (version.startsWith('4.')) {
                                // Scan upstream for relevant changes
                                    def yamlData = readYaml text: buildlib.doozer(
                                        """
                                        --group 'openshift-${version}'
                                        config:scan-sources --yaml
                                        """, [capture: true]
                                    )
                                    def changed = buildlib.getChanges(yamlData)
                                    if ( changed.rpms || changed.images ) {
                                        echo "Detected source changes: ${changed}"
                                        scheduleBuild = true
                                    }

                                }

                                upstream = "release-${version}"
                                downstream = "enterprise-${version}"
                                sh "./merge_ocp.sh ${mergeWorking} ${downstream} ${upstream}"


                                dir(mergeWorking) {
                                    // diff --stat will return nothing if there is nothing to push
                                    diffstat = sh(returnStdout: true, script: "git diff --cached --stat origin/${downstream}").trim()

                                    if (diffstat != "") {
                                        echo "New commits from openshift/origin merge:\n${diffstat}"
                                        sh "git push origin ${downstream}:${downstream}"
                                        scheduleBuild = true
                                    } else{
                                        echo "${downstream} openshift/ose was already up to date. Nothing to merge."
                                    }
                                }

                                successful.add(version)
                                echo "Success running ${version} merge"

                                if (params.SCHEDULE_INCREMENTAL && scheduleBuild) {
                                    build(
                                        job: 'build%2Focp4',
                                        propagate: false,
                                        wait: false,
                                        parameters: [
                                            string(name: 'BUILD_VERSION', value: version),
                                            booleanParam(name: 'FORCE_BUILD', value: false),
                                        ]
                                    )
                                    currentBuild.description += "triggered build: ${version}\n"
                                }

                            }

                        } else {
                            echo "Looks like there is another build ongoing for ${version} -- skipping for this run"
                        }

                    } catch (err) {
                        currentBuild.result = "UNSTABLE"
                        currentBuild.description += "failed to merge ${version}\n"
                        echo "Error running ${version} merge:\n${err}"

                        commonlib.email(
                            to: "${params.MAIL_LIST_FAILURE}",
                            from: "aos-art-automation@redhat.com",
                            replyTo: "aos-team-art@redhat.com",
                            subject: "Error merging OCP v${version}",
                            body: "Encountered an error while running OCP merge:\n${env.BUILD_URL}\n\n${err}"
                        )
                    }
                }
            }
        }

        if (!successful) {
            // no merges succeeded, consider it a failed build.
            currentBuild.result = "FAILURE"
        } else if (params.MAIL_LIST_SUCCESS.trim()) {
            // success email only if requested for this build
            commonlib.email(
                to: "${params.MAIL_LIST_SUCCESS}",
                from: "aos-art-automation@redhat.com",
                replyTo: "aos-team-art@redhat.com",
                subject: "Success merging OCP versions: ${successful.join(', ')}",
                body: "Success running OCP merges:\n${env.BUILD_URL}"
            )
        }

    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Unexpected error during OCP Merge!",
            body: "Encountered an unexpected error while running OCP merge: ${err}"
        )

        throw err
    }
}

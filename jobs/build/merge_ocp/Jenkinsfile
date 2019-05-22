node {
    checkout scm
    def commonlib = load("pipeline-scripts/commonlib.groovy")

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
                    [
                        name: 'COMMIT_DEPTH',
                        description: 'How deep to clone to ensure merges have a common base',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "100"
                    ],
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
                            'aos-team-art@redhat.com',
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
    commitDepth = params.COMMIT_DEPTH.trim().toInteger()

    currentBuild.displayName = "#${currentBuild.number} Merging versions ${params.VERSIONS}"
    currentBuild.description = ""

    try {
        successful = []
        sshagent(["openshift-bot"]) {
            stage("Clone ose") {
                sh "rm -rf ${mergeWorking}"
                sh "git clone ${downstreamRemote} --single-branch --branch master --depth 1 ${mergeWorking}"
                dir(mergeWorking) {
                    sh "git remote add upstream ${upstreamRemote}"
                }
            }

            stage("Merge") {
                for(int i = 0; i < mergeVersions.size(); ++i) {
                    def version = mergeVersions[i]
                    try {

                        if(version == commonlib.ocp4MasterVersion) {
                            sh "./merge_ocp.sh ${mergeWorking} master master ${commitDepth}"
                        } else {
                            upstream = "release-${version}"
                            downstream = "enterprise-${version}"
                            sh "./merge_ocp.sh ${mergeWorking} ${downstream} ${upstream} ${commitDepth}"
                        }

                        successful.add(version)
                        echo "Success running ${version} merge"

                    } catch (err) {
                        currentBuild.result = "UNSTABLE"
                        currentBuild.description += "failed to merge ${version}\n"
                        echo "Error running ${version} merge:\n${err}"

                        commonlib.email(
                            to: "${params.MAIL_LIST_FAILURE}",
                            from: "aos-team-art@redhat.com",
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
                from: "aos-team-art@redhat.com",
                subject: "Success merging OCP versions: ${successful.join(', ')}",
                body: "Success running OCP merges:\n${env.BUILD_URL}"
            )
        }

    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Unexpected error during OCP Merge!",
            body: "Encountered an unexpected error while running OCP merge: ${err}"
        )

        throw err
    }
}

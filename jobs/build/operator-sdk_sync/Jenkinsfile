node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("operator-sdk_sync", """
        <h2>Sync operator-sdk to mirror</h2>
        <b>Timing</b>: Manually, upon request. Expected to happen once every y-stream and
        sporadically on z-stream releases.
    """)

    properties([
        disableResume(),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                commonlib.ocpVersionParam('BUILD_VERSION'),
                string(
                    name: 'ASSEMBLY',
                    description: 'Under which ASSEMBLY directory to place the binaries.',
                    defaultValue: "",
                    trim: true,
                ),
                booleanParam(
                    name: 'UPDATE_LATEST_SYMLINK',
                    description: 'You need to update "latest" on the highest 4.x version',
                    defaultValue: false,
                ),
                string(
                    name: 'BUILD_NVR',
                    description: 'If QE request specific build, use nvr as parameter and it will ignore assembly.',
                    defaultValue: "",
                    trim: true,
                ),
                booleanParam(
                    name: 'USE_PRE_RELEASE',
                    description: 'Use pre-release as directory name if requested by QE',
                    defaultValue: false,
                ),
                string(
                    name: "ARCHES",
                    description: "Defaults to all arches in the build",
                    defaultValue: "amd64,arm64,ppc64le,s390x",
                    trim: true,
                )
            ]
        ],
    ])
    stage('operator-sdk-sync') {
        script {
            sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
            currentBuild.displayName += " ${params.ASSEMBLY}"
            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config=./config/artcd.toml",
                "operator-sdk-sync",
                "--group=openshift-${params.BUILD_VERSION}",
                "--assembly=${params.ASSEMBLY}",
            ]
            if (params.BUILD_NVR) {
                cmd << "--nvr" << params.BUILD_NVR
            }
            if (params.USE_PRE_RELEASE) {
                cmd << "--prerelease"
            }
            if (params.UPDATE_LATEST_SYMLINK) {
                cmd << "--updatelatest"
            }
            if (params.ARCHES) {
                def arches = commonlib.cleanCommaList(params.ARCHES)
                cmd << "--arches=${arches}"
            }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([aws(credentialsId: 's3-art-srv-enterprise', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'),
                                string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN')]) {
                    def out = sh(script: cmd.join(' '), returnStdout: true).trim()
                    echo out
                    if (out.contains('failed with')) {
                        currentBuild.result = "FAILURE"
                    }
                } // withCredentials
            } // withAppCiAsArtPublish
        } //script
    } // stage
} // node

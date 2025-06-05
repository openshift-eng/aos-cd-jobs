node() {
    wrap([$class: "BuildUser"]) {
        // gomod created files have filemode 444. It will lead to a permission denied error in the next build.
        sh "chmod u+w -R ."
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("prepare-release-konflux", """
            <h2>Prepare an OCP release to release via Konflux</h2>
        """)

        properties(
            [
                disableResume(),
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: "30",
                        artifactNumToKeepStr: "",
                        daysToKeepStr: "30",
                        numToKeepStr: "")),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                        commonlib.artToolsParam(),
                        string(
                            name: "ASSEMBLY",
                            description: "The name of the associated assembly",
                            defaultValue: "test",
                            trim: true
                        ),
                        string(
                            name: "BUILD_REPO_URL",
                            description: "(Optional) Override build-data repo. Defaults to group branch - to use a different branch/commit use repo@branch. e.g. https://github.com/thegreyd/ocp-build-data@prep-shipment-4.19.ec5",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: "SHIPMENT_REPO_URL",
                            description: "(Optional) Override shipment-data repo for opening shipment MR. Target branch will be `main`",
                            defaultValue: "",
                            trim: true
                        ),
                        commonlib.dryrunParam(),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()
        stage("initialize") {
            currentBuild.displayName += " ${params.BUILD_VERSION} - ${params.ASSEMBLY}"
        }
        try {
            stage("build") {
                buildlib.cleanWorkdir("./artcd_working")
                sh "mkdir -p ./artcd_working"
                def cmd = [
                    "artcd",
                    "-v",
                    "--working-dir=./artcd_working",
                    "--config", "./config/artcd.toml",
                ]
                if (params.DRY_RUN) {
                    cmd += ["--dry-run"]
                }

                cmd += [
                    "prepare-release-konflux",
                    "--group", "openshift-${params.BUILD_VERSION}",
                    "--assembly", params.ASSEMBLY,
                ]
                if (params.SHIPMENT_REPO_URL) {
                    cmd += ["--shipment-repo-url", params.SHIPMENT_REPO_URL]
                }
                if (params.BUILD_REPO_URL) {
                    cmd += ["--build-repo-url", params.BUILD_REPO_URL]
                }
                echo "Will run ${cmd.join(' ')}"
                
                withCredentials([
                    string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                    string(credentialsId: 'art-bot-jenkins-gitlab', variable: 'GITLAB_TOKEN'),
                    string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                    string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                ]) {
                    commonlib.shell(script: cmd.join(' '))
                }
            }
        } finally {
            stage("save artifacts") {
                commonlib.safeArchiveArtifacts([
                    "artcd_working/email/**",
                    "artcd_working/**/*.json",
                    "artcd_working/**/*.log",
                ])
            }
        }
    }
}

node() {
    wrap([$class: "BuildUser"]) {
        // gomod created files have filemode 444. It will lead to a permission denied error in the next build.
        sh "chmod u+w -R ."
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("konflux-release", """
            <h2>Create a Konflux Release</h2>
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
                        booleanParam(
                            name: "FORCE",
                            description: "Proceed even if an already existing release/advisory is detected",
                            defaultValue: false
                        ),
                        string(
                            name: 'RELEASE_ENVIRONMENT',
                            description: 'The release environment to operate on from the config file e.g. stage, prod',
                            defaultValue: '',
                            trim: true
                        ),
                        string(
                            name: 'KONFLUX_RELEASE_DATA_PATH',
                            description: '(Optional) konflux-release-data fork to use (e.g. release definition in your own fork). To point to a branch/commit use repo@commitish',
                            defaultValue: "https://gitlab.cee.redhat.com/hybrid-platforms/art/konflux-release-data",
                            trim: true,
                        ),
                        string(
                            name: 'CONFIG_FILENAME',
                            description: '(Optional) Release config filename to use. Defaults to assembly name',
                            defaultValue: '',
                            trim: true
                        ),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: true
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()
        stage("initialize") {
            def name = params.ASSEMBLY
            if (params.CONFIG_FILENAME) {
                name = params.CONFIG_FILENAME
            }
            currentBuild.displayName += " ${params.BUILD_VERSION} - ${name}"
            if (params.RELEASE_ENVIRONMENT) {
                currentBuild.displayName += " ${params.RELEASE_ENVIRONMENT}"
            }
            if (params.DRY_RUN) {
                currentBuild.displayName = "[DRY RUN] " + currentBuild.displayName
            }
        }
        try {
            stage("build") {
                buildlib.cleanWorkdir("./artcd_working")
                sh "mkdir -p ./artcd_working"
                def cmd = [
                    "artcd",
                    "-vv",
                    "--working-dir=./artcd_working",
                    "--config", "./config/artcd.toml",
                ]

                if (params.DRY_RUN) {
                    cmd << "--dry-run"
                }
                cmd += [
                    "konflux-release",
                    "--konflux-release-path", params.KONFLUX_RELEASE_DATA_PATH,
                    "--group", "openshift-${params.BUILD_VERSION}",
                    "--assembly", params.ASSEMBLY,
                    params.RELEASE_ENVIRONMENT,
                ]
                if (params.FORCE) {
                    cmd << "--force"
                }
                if (params.CONFIG_FILENAME) {
                    cmd << "--config-filename=${params.CONFIG_FILENAME}"
                }
                withCredentials([
                    file(credentialsId: 'openshift-bot-ocp-konflux-service-account', variable: 'KONFLUX_SA_KUBECONFIG'),
                    string(credentialsId: 'sid-gitlab-access-token', variable: 'GITLAB_TOKEN'),
                    file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    string(credentialsId: 'konflux-art-images-username', variable: 'KONFLUX_ART_IMAGES_USERNAME'),
                    string(credentialsId: 'konflux-art-images-password', variable: 'KONFLUX_ART_IMAGES_PASSWORD'),
                ]) {
                    echo "Will run ${cmd}"
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

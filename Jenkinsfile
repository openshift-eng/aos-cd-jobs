node() {
    wrap([$class: "BuildUser"]) {
        // gomod created files have filemode 444. It will lead to a permission denied error in the next build.
        sh "chmod u+w -R ."
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("functional-tests", """
            <h2>Run art-tools functional test suite</h2>
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
                        string(
                            name: 'MAKE_TARGETS',
                            description: 'The make targets to run (comma separated)',
                            defaultValue: 'functional-elliott',
                            trim: true,
                        ),
                        commonlib.artToolsParam(),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()
        stage("initialize") {
            currentBuild.displayName += " [$params.MAKE_TARGETS]"
        }
        stage("build") {
            withCredentials([
                string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                file(credentialsId: 'konflux-gcp-app-creds-prod', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
            ]) {
                dir("${env.WORKSPACE}/art-tools") {
                    for (String target : params.MAKE_TARGETS.split(',')) {
                        target = target.trim()
                        echo "Building target: ${target}"
                        // make doesn't inherit / work with jenkins's withEnv directive
                        // explicitly pass in PATH which has uv path for make tasks
                        commonlib.shell(script: "PATH=~/.cargo/bin:$PATH make ${target}")
                    }
                }
            }
        }
    }
}

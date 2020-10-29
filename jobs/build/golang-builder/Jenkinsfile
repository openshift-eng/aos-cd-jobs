node {
    cleanWs(cleanWhenFailure: false)
    checkout scm
    buildlib = load("pipeline-scripts/buildlib.groovy")
    commonlib = buildlib.commonlib
    commonlib.describeJob("golang-builder", """
        <h2>Build golang-builder images</h2>
        <b>Timing</b>: This is only ever run by humans, as needed. No job should be calling it.
    """)
    properties([
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                commonlib.dryrunParam(),
                commonlib.mockParam(),
                string(
                    name: 'GOLANG_VERSION',
                    description: 'Golang version (e.g. 1.14.1)',
                    trim: true,
                ),
                string(
                        name: 'RELEASE',
                        description: '(Optional) Release string for build instead of default (timestamp.el8 or timestamp.el7)',
                        trim: true,
                ),
                choice(
                    name: 'RHEL_VERSION',
                    description: 'for which RHEL version (7 or 8)',
                    choices: ['8', '7'].join('\n'),
                ),
                commonlib.suppressEmailParam(),
                string(
                    name: 'MAIL_LIST_SUCCESS',
                    description: '(Optional) Success Mailing List',
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: 'MAIL_LIST_FAILURE',
                    description: 'Failure Mailing List',
                    defaultValue: [
                        'aos-art-automation+failed-custom-build@redhat.com',
                    ].join(','),
                    trim: true,
                ),
            ],
        ],
    ])
    commonlib.checkMock()
}

pipeline {
    agent any

    options {
        disableResume()
        skipDefaultCheckout()
        timestamps()
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '365',
                daysToKeepStr: '365')
        )
    }
    stages {
        stage('set build info') {
            steps {
                script {
                    if (!(params.GOLANG_VERSION ==~ /\d+\.\d+\.\d+/))
                        error("Invalid Golang version ${params.GOLANG_VERSION}")
                    env._GOLANG_MAJOR_MINOR = commonlib.extractMajorMinorVersion(params.GOLANG_VERSION)
                    def group = params.RHEL_VERSION == "7" ? "golang-${env._GOLANG_MAJOR_MINOR}" : "rhel-${params.RHEL_VERSION}-golang-${env._GOLANG_MAJOR_MINOR}"
                    env._DOOZER_OPTS = "--working-dir ${WORKSPACE}/doozer_working --group $group"
                    currentBuild.displayName = "${params.GOLANG_VERSION}"
                }
            }
        }
        stage('build') {
            steps {
                script {
                    lock("golang-builder-lock-${env._GOLANG_MAJOR_MINOR}-el${params.RHEL_VERSION}") {
                        echo "Rebasing..."
                        def opts = "${env._DOOZER_OPTS} images:rebase --version v${params.GOLANG_VERSION}"
                        release = params.RELEASE ?: "${new Date().format("yyyyMMddHHmm")}.el${params.RHEL_VERSION}"
                        currentBuild.displayName += "-${release}"
                        opts += " --release ${release}  -m 'bumping to ${params.GOLANG_VERSION}-${release}'"
                        if (!params.DRY_RUN)
                            opts += " --push"
                        buildlib.doozer(opts)
                        echo "Building..."
                        opts = "${env._DOOZER_OPTS} images:build --repo-type unsigned --push-to-defaults"
                        if (params.DRY_RUN)
                            opts += " --dry-run"
                        buildlib.doozer(opts)
                    }
                }
            }
        }
    }
    post {
        always {
            script {
                commonlib.compressBrewLogs()
                commonlib.safeArchiveArtifacts([
                    "doozer_working/*.log",
                    "doozer_working/*.yaml",
                    "doozer_working/brew-logs/**",
                ])
            }
        }
        success {
            script {
                if (params.MAIL_LIST_SUCCESS.trim()) {
                    commonlib.email(
                        to: params.MAIL_LIST_SUCCESS,
                        from: "aos-team-art@redhat.com",
                        subject: "Successful golang-builder build: ${currentBuild.displayName}",
                        body: "Jenkins job: ${commonlib.buildURL()}\n${currentBuild.description}",
                    )
                }
            }
        }
        failure {
            script {
                currentBuild.description += "\nerror: ${err.getMessage()}"
                commonlib.email(
                    to: "${params.MAIL_LIST_FAILURE}",
                    from: "aos-team-art@redhat.com",
                    subject: "Error building golang-builder: ${currentBuild.displayName}",
                    body: """Encountered an error while running OCP pipeline:

${currentBuild.description}

Jenkins job: ${commonlib.buildURL()}
Job console: ${commonlib.buildURL('console')}
                """)
            }
        }
    }
}

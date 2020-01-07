#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def commonlib = build.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'DRY_RUN',
                        description: 'Take no action, just echo what the build would have done.',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    [
                        name: 'NEW_VERSION',
                        description: '(Optional) version for build instead of most recent\nor "+" to bump most recent version',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'FORCE_BUILD',
                        description: 'Build regardless of whether source has changed',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'BUILD_RPMS',
                        description: 'Which RPMs are candidates for building? "only/except" refer to list below',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "all",
                            "only",
                            "except",
                            "none",
                        ].join("\n"),
                        defaultValue: true
                    ],
                    [
                        name: 'RPM_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_RPMS (e.g. openshift,openshift-kuryr)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'BUILD_IMAGES',
                        description: 'Which images are candidates for building? "only/except" refer to list below',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: [
                            "all",
                            "only",
                            "except",
                            "none",
                        ].join("\n"),
                        defaultValue: true
                    ],
                    [
                        name: 'IMAGE_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_IMAGES (e.g. logging-kibana5,openshift-jenkins-2)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List\naos-cicd@redhat.com,aos-qe@redhat.com',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: "",
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-ocp4-build@redhat.com'
                        ].join(',')
                    ],
                    [
                        name: 'SPECIAL_NOTES',
                        description: '(Optional) special notes to include in the build email',
                        $class: 'hudson.model.TextParameterDefinition',
                        defaultValue: ""
                    ],
                ]
            ],
        ]
    )

    commonlib.checkMock()

    currentBuild.description = ""
    try {

        sshagent(["openshift-bot"]) {
            // To work on private repos, buildlib operations must run
            // with the permissions of openshift-bot
            lock("github-activity-lock-${params.BUILD_VERSION}") {
                stage("initialize") { build.initialize() }
                buildlib.assertBuildPermitted(doozerOpts)
                stage("build RPMs") { build.stageBuildRpms() }
                stage("build compose") { build.stageBuildCompose() }
                stage("update dist-git") { build.stageUpdateDistgit() }
                stage("build images") { build.stageBuildImages() }
                stage("mirror RPMs") { build.stageMirrorRpms() }
                stage("sync images") { build.stageSyncImages() }
                stage("sweep") {
                    if (!params.DRY_RUN) {
                        buildlib.sweep(params.BUILD_VERSION, true)
                    }
                }
            }
        }
        stage("report success") { build.stageReportSuccess() }
    } catch (err) {

        if (!buildlib.isBuildPermitted(doozerOpts)) {
            echo 'Exiting because this build is not permitted: ${err}'
            return
        }

        currentBuild.description += "\n-----------------\n\n${err}"
        currentBuild.result = "FAILURE"

        if (params.MAIL_LIST_FAILURE.trim()) {
            commonlib.email(
                to: params.MAIL_LIST_FAILURE,
                from: "aos-team-art@redhat.com",
                subject: "Error building OCP ${params.BUILD_VERSION}",
                body:
"""\
Pipeline build "${currentBuild.displayName}" encountered an error:
${currentBuild.description}


View the build artifacts and console output on Jenkins:
    - Jenkins job: ${commonlib.buildURL()}
    - Console output: ${commonlib.buildURL('console')}

"""
            )
        }
        throw err  // gets us a stack trace FWIW
    } finally {
        commonlib.safeArchiveArtifacts([
            "doozer_working/*.log",
            "doozer_working/brew-logs/**",
            "doozer_working/*.yaml",
            "doozer_working/*.yml",
        ])
    }
}

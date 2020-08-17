#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def commonlib = build.commonlib
    commonlib.describeJob("ocp4", """
        ------------------------------------------------
        Build OCP 4.y components incrementally
        ------------------------------------------------
        Timing: Usually run automatically from merge_ocp.
        Humans may run as needed. Locks prevent conflicts.

        In typical usage, scans for changes that could affect package or image
        builds and rebuilds the affected components.  Creates new plashets on
        each run, and runs other jobs to sync builds to nightlies, create
        operator metadata, and sweep bugs and builds into advisories.

        May also build unconditionally or with limited components.
    """)


    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '365',
                    daysToKeepStr: '365')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    booleanParam(
                        name: 'DRY_RUN',
                        description: 'Take no action, just echo what the build would have done.',
                        defaultValue: false
                    ),
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'NEW_VERSION',
                        description: '(Optional) version for build instead of most recent\nor "+" to bump most recent version',
                        defaultValue: ""
                    ),
                    booleanParam(
                        name: 'FORCE_BUILD',
                        description: 'Build regardless of whether source has changed',
                        defaultValue: false
                    ),
                    choice(
                        name: 'BUILD_RPMS',
                        description: 'Which RPMs are candidates for building? "only/except" refer to list below',
                        choices: [
                            "all",
                            "only",
                            "except",
                            "none",
                        ].join("\n"),
                    ),
                    string(
                        name: 'RPM_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_RPMS (e.g. openshift,openshift-kuryr)',
                        defaultValue: ""
                    ),
                    choice(
                        name: 'BUILD_IMAGES',
                        description: 'Which images are candidates for building? "only/except" refer to list below',
                        choices: [
                            "all",
                            "only",
                            "except",
                            "none",
                        ].join("\n"),
                    ),
                    string(
                        name: 'IMAGE_LIST',
                        description: '(Optional) Comma/space-separated list to include/exclude per BUILD_IMAGES (e.g. logging-kibana5,openshift-jenkins-2)',
                        defaultValue: ""
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: '(Optional) Success Mailing List\naos-cicd@redhat.com,aos-qe@redhat.com',
                        defaultValue: "",
                    ),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-ocp4-build@redhat.com'
                        ].join(',')
                    ),
                    string(
                        name: 'SPECIAL_NOTES',
                        description: '(Optional) special notes to include in the build email',
                        defaultValue: ""
                    ),
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
                lock("compose-lock-${params.BUILD_VERSION}") {
                    stage("build compose") { build.stageBuildCompose() }
                }
                stage("update dist-git") { build.stageUpdateDistgit() }
                stage("build images") { build.stageBuildImages() }
            }
            lock("mirroring-rpms-lock-${params.BUILD_VERSION}") {
                stage("mirror RPMs") { build.stageMirrorRpms() }
            }
            stage("sync images") { build.stageSyncImages() }
            stage("sweep") {
                if (!params.DRY_RUN) {
                    buildlib.sweep(params.BUILD_VERSION, true)
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
        commonlib.compressBrewLogs()
        commonlib.safeArchiveArtifacts([
            "doozer_working/*.log",
            "doozer_working/brew-logs.tar.bz2",
            "doozer_working/*.yaml",
            "doozer_working/*.yml",
        ])
        buildlib.cleanWorkdir(build.doozerWorking)
    }
}

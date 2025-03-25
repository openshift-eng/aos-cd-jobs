#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '30',
                    daysToKeepStr: '30')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.mockParam(),
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    choice(
                        name: 'JOB_NAME',
                        description: 'RHCOS job name to trigger',
                        choices: ['build'],
                    ),
                    booleanParam(
                        name: 'NEW_BUILD',
                        description: '(Multi pipeline only) Request a new build from the RHCOS pipeline even when it finds no changes from the last.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'IGNORE_RUNNING',
                        description: '(Multi pipeline only) Request a build from the RHCOS pipeline even if one is already in progress (instead of aborting like usual). Still only one runs at a time. Only for use by humans, really, and you probably want NEW_BUILD with this.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: "DRY_RUN",
                        description: "Take no action, just echo what the job would have done.",
                        defaultValue: false
                    ),
                    commonlib.artToolsParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()
    currentBuild.displayName = "#${currentBuild.number} - ${params.BUILD_VERSION}: "
    currentBuild.description = "RHCOS ${params.BUILD_VERSION}\n"
    def skipBuild = true  // global variable to track if we skip the remote build

    try {
        // Disabling compose lock for now. Ideally we achieve a stable repo for RHCOS builds in the future,
        // but for now, being this strict is slowing down the delivery of nightlies.
        //lock("compose-lock-${params.BUILD_VERSION}") {
        def lockval = params.DRY_RUN ? "rhcos-lock-${params.BUILD_VERSION}-dryrun" : "rhcos-lock-${params.BUILD_VERSION}"
        lock(resource: lockval, skipIfLocked: true) {  // wait for all to succeed or fail for this version before starting more
            skipBuild = false
            echo "triggering rhcos builds"
            buildlib.init_artcd_working_dir()

            def dryrun = params.DRY_RUN ? '--dry-run' : ''
            def run_multi_build = {
                withCredentials([file(credentialsId: 'rhcos--prod-pipeline_jenkins_api-prod-stable-spoke1-dc-iad2-itup-redhat-com', variable: 'KUBECONFIG')]) {
                    // we want to see the stderr as it runs, so will not capture with commonlib.shell;
                    // but somehow it is buffering the stderr anyway and [lmeyer] cannot figure out why.
                    def text = sh(returnStdout: true, script: """
                          no_proxy=api.ocp-virt.prod.psi.redhat.com,\$no_proxy \\
                          artcd ${dryrun} --config=./config/artcd.toml build-rhcos --version=${params.BUILD_VERSION} \\
                            --ignore-running=${params.IGNORE_RUNNING} --new-build=${params.NEW_BUILD} --job=${params.JOB_NAME}
                    """)
                    echo text
                    if (params.DRY_RUN) {
                        skipBuild = true
                        return
                    }
                    def data = readJSON(text: text)
                    if (data["action"] == "skip") {
                        skipBuild = true
                    }
                }
            }
            try {
                // succeed or fail, RHCOS team do not want us to kick off builds too often
                parallel "multi": run_multi_build, "rate-limit": { sleep 60 * 60 * 2 }
            } catch (err) {
                currentBuild.displayName += " -- Failed"
                echo "Failure: ${err}"
                currentBuild.result = "FAILURE"
            }
        }
        if (skipBuild) {
            currentBuild.displayName += " -- Skipped"
            currentBuild.description += " -- skipped (build already in progress)"
            currentBuild.result = "ABORTED"
        }
    } finally {
    }
}

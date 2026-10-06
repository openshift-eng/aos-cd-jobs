#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("skip-release-wait", """
        <h2>Temporarily skip the nightly creation interval</h2>
        <p>Sets minCreationIntervalSeconds to a configurable low value (default 0) on a
        release stream's imagestream config annotation, waits a configurable period,
        then restores the original value.</p>
        <p>This allows ART to quickly get a new nightly after a rejection or failure,
        without the cumbersome PR-based workaround of editing the release stream config.</p>
        <p>Can also reset the interval to its original value by specifying the desired TARGET_INTERVAL_SECONDS.</p>
    """)

    properties([
        disableResume(),
        buildDiscarder(logRotator(daysToKeepStr: '30')),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                string(
                    name: 'VERSION',
                    description: 'Release version (e.g. "5.0", "4.18")',
                    trim: true,
                    defaultValue: ""
                ),
                choice(
                    name: 'PRODUCT',
                    description: 'Target product',
                    choices: ['OCP', 'OKD'].join('\n'),
                ),
                choice(
                    name: 'STREAM_TYPE',
                    description: 'Stream type',
                    choices: ['ART', 'CI'].join('\n'),
                ),
                string(
                    name: 'WAIT_MINUTES',
                    description: 'How long to wait (in minutes) before restoring the original config',
                    trim: true,
                    defaultValue: "30"
                ),
                string(
                    name: 'TARGET_INTERVAL_SECONDS',
                    description: 'Target value for minCreationIntervalSeconds. Default 0 effectively skips the wait. Set to the original value to restore the interval. Must be a non-negative integer.',
                    trim: true,
                    defaultValue: "0"
                ),
                booleanParam(
                    name: 'DRY_RUN',
                    description: 'When true, show what would be done without applying changes',
                    defaultValue: true
                ),
                commonlib.mockParam(),
            ]
        ],
    ])

    commonlib.checkMock()

    def targetInterval = params.TARGET_INTERVAL_SECONDS
    if (!targetInterval.isInteger() || targetInterval.toInteger() < 0) {
        error("TARGET_INTERVAL_SECONDS must be a non-negative integer, got: ${targetInterval}")
    }

    def namespace = ""
    def imagestream = ""
    def originalConfig = ""
    def newConfig = ""

    timestamps {

    stage('Validate parameters') {
        if (!params.VERSION) {
            error("VERSION is required")
        }
        if (!(params.VERSION ==~ /\d+\.\d+/)) {
            error("VERSION must be in X.Y format (e.g. 4.18), got: ${params.VERSION}")
        }
        if (params.PRODUCT == 'OKD' && params.STREAM_TYPE == 'CI') {
            error("OKD does not use CI imagestreams")
        }

        if (params.PRODUCT == 'OCP') {
            namespace = "ocp"
            if (params.STREAM_TYPE == 'ART') {
                imagestream = "${params.VERSION}-art-latest"
            } else {
                imagestream = "${params.VERSION}"
            }
        } else {
            // OKD + ART
            namespace = "origin"
            imagestream = "scos-${params.VERSION}-art"
        }

        def dry_run_label = params.DRY_RUN ? '[DRY_RUN]' : ''
        currentBuild.displayName = "${namespace}/${imagestream} ${dry_run_label}"
        currentBuild.description = "v${params.VERSION} ${params.PRODUCT}/${params.STREAM_TYPE} → interval=${targetInterval}s" + (params.DRY_RUN ? " (dry-run)" : "")

        echo "Namespace: ${namespace}"
        echo "Imagestream: ${imagestream}"
    }

    stage('Read current config') {
        buildlib.withAppCiAsArtPublish() {
            originalConfig = commonlib.shell(
                script: "oc -n ${namespace} get is ${imagestream} -o jsonpath='{.metadata.annotations.release\\.openshift\\.io/config}'",
                returnStdout: true
            ).trim()
        }

        if (!originalConfig) {
            error("Failed to read release.openshift.io/config annotation from ${namespace}/${imagestream}")
        }

        echo "Original config (${originalConfig.length()} chars):\n${originalConfig}"
        echo "Original config size: ${originalConfig.length()} characters"
    }

    stage('Compute modified config') {
        // Write original config to a temp file to avoid shell quoting issues,
        // then use jq -c to set minCreationIntervalSeconds to the target value
        writeFile file: "original-config.json", text: originalConfig
        newConfig = commonlib.shell(
            script: "jq -c '.minCreationIntervalSeconds = ${targetInterval}' original-config.json",
            returnStdout: true
        ).trim()

        echo "New config (${newConfig.length()} chars):\n${newConfig}"
        echo "New config size: ${newConfig.length()} characters"

        // Write new config to a file so we can use it safely in the annotate command
        writeFile file: "new-config.json", text: newConfig

        def annotateCmd = "oc -n ${namespace} annotate is ${imagestream} --overwrite 'release.openshift.io/config=\$(cat new-config.json)'"
        echo "Command to apply:\n${annotateCmd}"
    }

    stage('Apply') {
        if (params.DRY_RUN) {
            echo "DRY RUN: Would execute the above command, wait ${params.WAIT_MINUTES} minutes, then restore original config"
            return
        }

        buildlib.withAppCiAsArtPublish() {
            // Write config files into the workspace for safe shell usage
            writeFile file: "new-config.json", text: newConfig
            writeFile file: "original-config.json", text: originalConfig

            echo "Applying modified config to ${namespace}/${imagestream}..."
            commonlib.shell(
                script: "oc -n ${namespace} annotate is ${imagestream} --overwrite \"release.openshift.io/config=\$(cat new-config.json)\""
            )
            echo "Successfully applied modified config (minCreationIntervalSeconds=${targetInterval})"

            echo "Waiting ${params.WAIT_MINUTES} minutes before restoring original config..."
            sleep time: params.WAIT_MINUTES.toInteger(), unit: 'MINUTES'

            echo "Restoring original config to ${namespace}/${imagestream}..."
            commonlib.shell(
                script: "oc -n ${namespace} annotate is ${imagestream} --overwrite \"release.openshift.io/config=\$(cat original-config.json)\""
            )
            echo "Successfully restored original config"
        }
    }

    }
}

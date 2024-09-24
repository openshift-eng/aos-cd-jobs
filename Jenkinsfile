#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("sigstore-sign", """
        Sign a release with the sigstore method.
    """)


    // Expose properties for a parameterized build
    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('VERSION', '4'),
                    commonlib.artToolsParam(),
                    string(
                        name: 'RELEASE',
                        description: 'The name of a release assembly to sign.',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    string(
                        name: 'IMAGE_PULLSPECS',
                        description: 'List of images to recursively sign (must correspond to RELEASE). If not supplied, look up release images from assembly.',
                        trim: true,
                    ),
                    choice(
                        name: 'SIGNING_KEY',
                        description: 'Which key to sign with',
                        choices: ["production", "stage"].join("\n"),
                    ),
                    choice(
                        name: 'SIGN_RELEASE_IMAGES',
                        description: 'Sign the release images?',
                        choices: ["yes", "only", "no"].join("\n"),
                    ),
                    booleanParam(
                        name: 'VERIFY_RELEASE_IMAGES',
                        description: 'Check that release images have legacy signatures (REQUIRED when looking up pullspecs)',
                        defaultValue: true,
                    ),
                    commonlib.dryrunParam('Do not actually sign anything'),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.VERSION)
    currentBuild.displayName += " ${params.VERSION} - ${params.RELEASE}"

    stage("initialize") {
        // must be able to access and update quay registry
        buildlib.registry_quay_dev_login()
        buildlib.init_artcd_working_dir()
    }

    stage("sign") {
        def cmd = [
            "artcd",
            "-v",
            "--working-dir=./artcd_working",
            "--config=./config/artcd.toml",
        ]
        if (params.DRY_RUN) cmd << "--dry-run"
        cmd += [
            "sigstore-sign",
            "--group=openshift-${params.VERSION}",
            "--assembly=${params.RELEASE}",
            "--sign-release=${params.SIGN_RELEASE_IMAGES}",
        ]
        if (params.VERIFY_RELEASE_IMAGES) cmd << "--verify-release"
        cmd << "--"  // no more options, just pullspecs
        cmd += commonlib.parseList(params.IMAGE_PULLSPECS)
        def signing_creds_file = params.SIGNING_KEY == "production" ? "kms_prod_release_signing_creds_file" : "kms_stage_release_signing_creds_file"
        def signing_key_id = params.SIGNING_KEY == "production" ? "kms_prod_release_signing_key_id" : "kms_stage_release_signing_key_id"
        withCredentials([
            string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
            file(credentialsId: signing_creds_file, variable: 'KMS_CRED_FILE'),
            string(credentialsId: signing_key_id, variable: 'KMS_KEY_ID'),
            string(credentialsId: 'signing_rekor_url', variable: 'REKOR_URL'),
        ]) {
            commonlib.shell(cmd.join(" "))
        }
    }

    stage("clean") {
        buildlib.cleanWorkspace()
    }

}

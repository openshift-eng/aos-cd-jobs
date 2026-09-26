#!/usr/bin/env groovy

node() {
    timestamps {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("sign-existing-releases", """
        <h2>Retroactively sign existing release payloads (and their referenced components) with Sigstore/cosign</h2>
        <b>Timing</b>: Run manually, on demand.

        Runs the standalone <code>pyartcd/hack/sign_existing_releases.py</code> tool against
        release payloads that already exist in quay.io. It reuses the production
        <code>SigstoreSignatory</code> signing logic:
        <ul>
          <li>Release images are signed with <b>tag identity</b> only by default (digest
              signatures usually already exist for released payloads). Use <code>SIGN_DIGEST</code>
              to also create digest-identity signatures for the release images.</li>
          <li>Referenced component images are discovered by spidering each payload with
              <code>oc adm release info -o json</code> and are signed with <b>digest identity</b> only.
              Multi-arch references are expanded to and signed for every architecture.</li>
        </ul>
        <code>SIGN_RELEASE</code> selects the scope: <code>yes</code> (release images + components),
        <code>only</code> (release images only), or <code>no</code> (referenced components only).
    """)

    properties([
        disableResume(),
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '30',
                daysToKeepStr: '30',
                numToKeepStr: '300',
            )
        ),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                commonlib.artToolsParam(),
                text(
                    name: 'PULLSPECS',
                    description: 'Release image pullspecs to sign, one per line (blank lines and # comments ignored). ' +
                        'Tag-based pullspecs are required for release-image signing, e.g.\n' +
                        'quay.io/openshift-release-dev/ocp-release:4.16.4-multi',
                    defaultValue: '',
                ),
                choice(
                    name: 'SIGN_RELEASE',
                    description: 'What to sign: yes = release images + referenced components; ' +
                        'only = release images only; no = referenced components only.',
                    choices: ['yes', 'no', 'only'].join('\n'),
                ),
                booleanParam(
                    name: 'SIGN_DIGEST',
                    description: 'Also sign the release images with digest identity ' +
                        '(default: tag-only, appropriate for retroactive signing where digest signatures already exist). ' +
                        'Does not affect component images, which are always digest-only.',
                    defaultValue: false,
                ),
                string(
                    name: 'CONCURRENCY',
                    description: 'Maximum concurrent signing/discovery operations.',
                    defaultValue: '50',
                    trim: true,
                ),
                commonlib.dryrunParam('Do not actually sign anything; log what would be signed. Uses stage KMS credentials.'),
                commonlib.mockParam(),
            ],
        ]
    ])

    commonlib.checkMock()

    // Parse pullspecs: drop blank lines and comments.
    def pullspecs = params.PULLSPECS.split('\n').collect { it.trim() }.findAll { it && !it.startsWith('#') }

    currentBuild.displayName += " ${params.SIGN_RELEASE} (${pullspecs.size()} pullspec(s))"
    if (params.DRY_RUN) {
        currentBuild.displayName += " [DRY RUN]"
    }

    stage("Validate parameters") {
        if (!pullspecs) {
            error("PULLSPECS is required: provide at least one release image pullspec.")
        }
        if (!(params.CONCURRENCY?.trim() ==~ /\d+/)) {
            error("CONCURRENCY must be a positive integer.")
        }
        echo "Will sign:"
        echo "  scope (SIGN_RELEASE): ${params.SIGN_RELEASE}"
        echo "  sign release digest:  ${params.SIGN_DIGEST}"
        echo "  concurrency:          ${params.CONCURRENCY}"
        echo "  dry run:              ${params.DRY_RUN}"
        pullspecs.each { echo "  - ${it}" }
    }

    // Use stage signing infrastructure for dry runs, prod for real signing.
    def signing_env = params.DRY_RUN ? "stage" : "prod"
    def sigstore_creds_file = signing_env == "prod" ? "kms_prod_release_signing_creds_file" : "kms_stage_release_signing_creds_file"
    def sigstore_key_id = signing_env == "prod" ? "kms_prod_release_signing_key_id" : "kms_stage_release_signing_key_id"

    stage("sign-existing-releases") {
        def cmd = [
            "python",
            "./art-tools/pyartcd/hack/sign_existing_releases.py",
        ]

        if (params.DRY_RUN) {
            cmd << "--dry-run"
        }

        cmd += [
            "--sign-release", params.SIGN_RELEASE,
            "--concurrency", params.CONCURRENCY.trim(),
            "--file", "artcd_working/pullspecs.txt",
        ]

        if (params.SIGN_DIGEST) {
            cmd << "--sign-digest"
        }

        echo "Will run: ${cmd.join(' ')}"

        buildlib.withAppCiAsArtPublish() {
            withCredentials([
                // QUAY_AUTH_FILE grants read access to the private component repo
                // (quay.io/openshift-release-dev/ocp-v4.0-art-dev) for discovery, and is
                // used by cosign for registry credentials during signing.
                file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                // KMS credentials used by cosign to sign (only needed for non-dry-run).
                file(credentialsId: sigstore_creds_file, variable: 'KMS_CRED_FILE'),
                string(credentialsId: sigstore_key_id, variable: 'KMS_KEY_ID'),
                string(credentialsId: 'signing_rekor_url', variable: 'REKOR_URL'),
            ]) {
                withEnv(["BUILD_URL=${BUILD_URL}", "JOB_NAME=${JOB_NAME}"]) {
                    try {
                        buildlib.init_artcd_working_dir()
                        writeFile(file: "artcd_working/pullspecs.txt", text: pullspecs.join('\n') + '\n')
                        sh(script: cmd.join(' '))
                    } finally {
                        commonlib.safeArchiveArtifacts([
                            "artcd_working/**/*.txt",
                            "artcd_working/**/*.log",
                        ])
                        buildlib.cleanWorkspace()
                    }
                }
            }
        }
    }

    }
}

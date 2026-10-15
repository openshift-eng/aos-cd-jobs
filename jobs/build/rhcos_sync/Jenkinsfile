#!/usr/bin/env groovy

node {
    timestamps {
    checkout scm
    def rhcoslib = load("rhcoslib.groovy")
    def releaselib = rhcoslib.releaselib
    def buildlib = rhcoslib.buildlib
    def commonlib = rhcoslib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("rhcos_sync", """
        <h2>Sync the RHCOS boot images to mirror</h2>
        <ul><li>https://mirror.openshift.com/pub/openshift-v4/\$ARCH/dependencies/rhcos/</li></ul>
        Publishes RHCOS boot images for a particular release (according to the
        installer image manifest) so that customers can base their OCP 4
        installs on them. Also updates <code>latest</code> directory by default.

        Timing: At EC time and GA this gets run by automation. It may also be requested by teams to run at RC time.
        It may also be used when there is a boot-time bug requiring updated boot images in a version already
        released. See <a href="https://art-docs.engineering.redhat.com/release/4.y-ga/#publish-rhcos-bootimages" target="_blank">the docs</a>
        </p>
    """)


    properties(
        [
            disableResume(),
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: ''
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.artToolsParam(),
                    string(
                        name: 'RELEASE_TAG',
                        description: 'Release Name (or pullspec with a tag) from which to get RHCOS buildID reference (ex. 4.12.0-ec.2-x86_64). <b>Note:</b> The buildID is pulled from the installer image in the payload, which is often different from what is in the rhcos image - so make sure the installer image points to the right buildID.',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'FORCE',
                        description: 'Download and sync items even if it is deemed unnecessary',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'NO_LATEST',
                        description: 'Do not update the <b>latest</b> directory',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SIGN_ONLY',
                        description: 'Only sign RHCOS container images via Sigstore/cosign (skip boot image mirror sync, GPG signing, ROSA, Azure). Use for z-stream releases.',
                        defaultValue: false,
                    ),
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                ],
            ]
        ]
    )

    commonlib.checkMock()

    buildlib.initialize()

    if (!params.RELEASE_TAG) {
        error("Need RELEASE_TAG")
    }

    // === Minimal tag parsing (no oc commands) ===
    // The heavy lifting (pullspec resolution, oc image extract, RHCOS metadata,
    // synclist generation, needsHappening check) is now handled by artcd rhcos-sync.
    tag = params.RELEASE_TAG

    (major, minor) = commonlib.extractMajorMinorVersionNumbers(tag)
    ocpVersion = "$major.$minor"

    // Handle pullspec-style tags: extract the tag portion for arch parsing
    if (tag.contains("/")) {
        if (!tag.contains(":")) error("RELEASE_TAG pullspec must include a :tag")
        tag = tag.split(":")[-1]
    }

    (arch, priv) = releaselib.getReleaseTagArchPriv(tag)

    // Derive the version name from the tag without oc commands.
    // For nightlies, use "dev-<version>"; for stable/pre-release, strip the arch suffix.
    noLatest = params.NO_LATEST
    if (tag.contains("nightly")) {
        name = "dev-${ocpVersion}"
        noLatest = true
    } else {
        name = tag.replaceAll("-${arch}\$", "")
        if (priv) {
            name = name.replaceAll("-priv\$", "")
        }
    }

    // Stable releases (e.g. 4.19.3-x86_64) go to the version directory;
    // everything else (EC, RC, nightly) goes to pre-release.
    pattern = /$major\.$minor\.(\d+)-$arch/
    is_stable = tag ==~ pattern
    mirrorPrefix = is_stable ? ocpVersion : "pre-release"

    currentBuild.displayName = "${name} - ${arch} - ${mirrorPrefix}"
    if (params.DRY_RUN) {
        currentBuild.displayName += " [DRY_RUN]"
    }
    if (params.SIGN_ONLY) {
        currentBuild.displayName += " [SIGN_ONLY]"
    }

    echo("RHCOS sync: tag=${tag}, arch=${arch}, ocpVersion=${ocpVersion}, name=${name}, mirrorPrefix=${mirrorPrefix}")

    try {
        // === Main stage: artcd rhcos-sync handles the entire sync + sign workflow ===
        // This replaces the previous Groovy preamble (pullspec resolution, oc image
        // extract, RHCOS metadata extraction, synclist generation, needsHappening
        // check) and the two separate artcd calls (sync-rhcos + sign-rhcos-containers).
        stage("Sync RHCOS boot images and sign containers") {
            def signing_env = params.DRY_RUN ? "stage" : "prod"
            def signing_cert_id = signing_env == "prod" ? "0xffe138e-openshift-art-bot" : "0xffe138d-nonprod-openshift-art-bot"
            def sigstore_creds_file = signing_env == "prod" ? "kms_prod_release_signing_creds_file" : "kms_stage_release_signing_creds_file"
            def sigstore_key_id = signing_env == "prod" ? "kms_prod_release_signing_key_id" : "kms_stage_release_signing_key_id"

            withCredentials([
                // Registry auth for pulling release payloads
                file(credentialsId: 'quay-auth-file', variable: 'QUAY_AUTH_FILE'),
                // S3 mirror credentials for boot image sync
                file(credentialsId: 'aws-credentials-file', variable: 'AWS_SHARED_CREDENTIALS_FILE'),
                string(credentialsId: 's3-art-srv-enterprise-cloudflare-endpoint', variable: 'CLOUDFLARE_ENDPOINT'),
                // GPG signing credentials for boot image sha256sum
                file(credentialsId: "${signing_cert_id}.crt", variable: 'SIGNING_CERT'),
                file(credentialsId: "${signing_cert_id}.key", variable: 'SIGNING_KEY'),
                // Sigstore/cosign credentials for container image signing
                file(credentialsId: sigstore_creds_file, variable: 'KMS_CRED_FILE'),
                string(credentialsId: sigstore_key_id, variable: 'KMS_KEY_ID'),
                string(credentialsId: 'signing_rekor_url', variable: 'REKOR_URL'),
            ]) {
                // KUBECONFIG provides oc access to registry.ci for nightly payloads
                buildlib.withAppCiAsArtPublish() {
                    buildlib.init_artcd_working_dir()
                    def dryrun = params.DRY_RUN ? "--dry-run" : ""
                    def forceFlag = params.FORCE ? "--force" : ""
                    def noLatestFlag = noLatest ? "--no-latest" : ""
                    def signOnlyFlag = params.SIGN_ONLY ? "--sign-only" : ""
                    def cmd = """
                        artcd -vv ${dryrun} \\
                            --config=${env.WORKSPACE}/config/artcd.toml \\
                            --working-dir=${env.WORKSPACE}/artcd_working \\
                            rhcos-sync \\
                            --release-tag ${params.RELEASE_TAG} \\
                            --signing-env ${signing_env} \\
                            ${forceFlag} \\
                            ${noLatestFlag} \\
                            ${signOnlyFlag}
                    """
                    commonlib.shell(script: cmd)
                }
            }
        }

        if (!params.SIGN_ONLY) {
            stage("Slack notification to release channel") {
                if (!params.DRY_RUN) {
                    slacklib.to(ocpVersion).say("""
                    *:white_check_mark: rhcos_sync (${mirrorPrefix}) successful*
                    https://mirror.openshift.com/pub/openshift-v4/${arch}/dependencies/rhcos/${mirrorPrefix}/${name}/

                    buildvm job: ${commonlib.buildURL('console')}
                    """)
                }
            }

            // Only run for x86_64 since no AMIs for other arches
            if (arch == "x86_64") {
                stage("Mirror ROSA AMIs") {
                    // The artcd rhcos-sync command writes the RHCOS stream JSON to
                    // the working directory. Extract the us-east-1 AMI from it and
                    // create a meta.json-compatible file for rosa_sync.sh.
                    def streamJsonFile = "${env.WORKSPACE}/artcd_working/rhcos-${arch}.json"
                    def ami = commonlib.shell(
                        returnStdout: true,
                        script: "jq -r '.architectures.x86_64.images.aws.regions[\"us-east-1\"].image // empty' ${streamJsonFile}"
                    ).trim()

                    if (!ami) {
                        echo "No us-east-1 AMI found in RHCOS stream data, skipping ROSA sync"
                        return
                    }

                    def rosaMetaJson = "${env.WORKSPACE}/rosa-meta.json"
                    writeFile file: rosaMetaJson, text: """{"amis": [{"name": "us-east-1", "hvm": "${ami}"}]}"""

                    withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', accessKeyVariable: 'AWS_ACCESS_KEY_ID', credentialsId: 'artjenkins_rhcos_rosa_marketplace_staging', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                        commonlib.shell("${env.WORKSPACE}/build-scripts/rosa-sync/rosa_sync.sh ${rosaMetaJson} ${params.DRY_RUN}")
                    }
                    withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', accessKeyVariable: 'AWS_ACCESS_KEY_ID', credentialsId: 'artjenkins_rhcos_rosa_marketplace_production', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                        commonlib.shell("${env.WORKSPACE}/build-scripts/rosa-sync/rosa_sync.sh ${rosaMetaJson} ${params.DRY_RUN}")
                    }
                }
                stage("Slack notification to release channel") {
                    if (!params.DRY_RUN) {
                        slacklib.to(ocpVersion).say("""
                        *:white_check_mark: rosa_sync (${name}) successful*
                        """)
                    }
                }
            }

            // Publish azure marketplace for 4.10+
            stage("Publish azure marketplace") {
                if (buildlib.cmp_version(ocpVersion, "4.9") == 1) {
                    build(
                        job: 'build%252Fpublish_azure_marketplace',
                        wait: false,
                        parameters: [
                            string(name: 'VERSION', value: ocpVersion),
                            booleanParam(name: 'DRY_RUN', value: params.DRY_RUN),
                        ]
                    )
                } else {
                    echo "Skipping publish azure marketplace due to ocpversion lower than 4.10."
                }
            }
        }
    } catch (err) {
        if (!params.DRY_RUN) {
            slacklib.to(ocpVersion).say("""
            *:heavy_exclamation_mark: rhcos_sync ${mirrorPrefix} failed*
            buildvm job: ${commonlib.buildURL('console')}
            """)
        }
        throw(err)
    } finally {
        commonlib.safeArchiveArtifacts(rhcoslib.artifacts)
        buildlib.cleanWorkspace()
    }
    }
}

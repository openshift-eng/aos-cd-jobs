#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("sign-rhacs", """
    Signs RHACS images as a temporary measure until they are onboarded with CPaaS.
    """)


    // Expose properties for a parameterized build
    properties(
        [
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    choice(
                        name: 'REPO',
                        description: 'The image repository',
                        choices: [
                            "main",
                            "roxctl",
                            "scanner",
                            "scanner-db",
                            "collector",
                        ].join("\n"),
                    ),
                    string(
                        name: 'VERSION',
                        description: 'e.g 0.5.4.1',
                        defaultValue: "",
                        trim: true,
                    ),
                    string(
                        name: 'SIGNATURE_NAME',
                        description: 'Signature name\nStart with signature-1 and only increment if adding an additional signature to a release!',
                        defaultValue: "signature-1",
                        trim: true,
                    ),
                    choice(
                        name: 'KEY_NAME',
                        description: 'For prod we currently use "redhatrelease2"',
                        choices: [
                            "redhatrelease2",
                        ].join("\n"),
                    ),
                    string(
                        name: 'DIGEST',
                        description: 'The digest of the release. Example value: "sha256:f28cbabd1227352fe704a00df796a4511880174042dece96233036a10ac61639"\nCan be taken from the Release job.',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.dryrunParam('Only do dry run test and exit\nDoes not send anything over the bus'),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()
    def workDir = "${env.WORKSPACE}/working"
    buildlib.cleanWorkdir(workDir)

    // must be able to access remote registry for verification
    buildlib.registry_quay_dev_login()

    stage('sign-artifacts') {
        def noop = params.DRY_RUN ? " --noop" : " "

        currentBuild.displayName += "- ${params.REPO}"
        if (params.DRY_RUN) {
            currentBuild.displayName += " (dry-run)"
            currentBuild.description = "[DRY RUN]"
        }

        requestIdSuffix = ""

        def digest = commonlib.sanitizeInvisible(params.DIGEST).trim()
        def digestParam = digest ? "--digest ${digest}" : ""
        if ( !(digest ==~ /sha256:[0-9a-f]{64}/) ) {
            currentBuild.description = "bad digest"
            error("The digest does not look like 'sha256:hex64'")
        }

        wrap([$class: 'BuildUser']) {
            def buildUserId = (env.BUILD_USER_ID == null) ? "automated-process" : env.BUILD_USER_ID
	    if ( buildUserId == "automated-process" ) {
		echo("Automated sign request started: manually setting signing requestor")
	    }
            echo("Submitting${noop} signing requests as user: ${buildUserId}")

            dir(workDir) {
                withCredentials([file(credentialsId: 'msg-openshift-art-signatory-prod.crt', variable: 'busCertificate'),
                                 file(credentialsId: 'msg-openshift-art-signatory-prod.key', variable: 'busKey')]) {
                    // ######################################################################
                    def baseUmbParams = buildlib.cleanWhitespace("""
                                --requestor "${buildUserId}" --sig-keyname ${params.KEY_NAME}
                                --release-name "rhacs.${params.REPO}-${params.VERSION}" --client-cert ${busCertificate}
                                --client-key ${busKey} --env prod
                            """)

                        def openshiftJsonSignParams = buildlib.cleanWhitespace("""
                             ${baseUmbParams} --product openshift --arch x86_64 --client-type ocp
                             --request-id 'openshift-json-digest-${env.BUILD_ID}${requestIdSuffix}' ${digestParam} ${noop}
                         """)

                        echo "Submitting RHACS Payload JSON claim signature request"
                        retry(3) {
                            timeout(time: 3, unit: 'MINUTES') {
                                commonlib.shell(
                                    script: "../umb_producer.py json-digest ${openshiftJsonSignParams}"
                                )
                            }
                        }

                }
            }
        }
    }

    stage('mirror artifacts') {
        mirrorTarget = "use-mirror-upload.ops.rhcloud.com"
        if (params.DRY_RUN) {
            echo "Would have archived artifacts in jenkins"
            echo "Would have mirrored artifacts to mirror.openshift.com/pub/:"
            echo "    invoke_on_use_mirror push.pub.sh MIRROR_PATH"
        } else {
            echo "Mirroring artifacts to mirror.openshift.com/pub/"

            dir(workDir) {
                try {
                    sshagent(["openshift-bot"]) {
                        sh """
                        set -o xtrace
                        set set -euo pipefail
                        fn=`ls sha256=*`
                        rm -rf staging
                        mkdir -p staging/rhacs
                        mkdir -p staging/rh-acs
                        cp \${fn} staging/rhacs/${params.REPO}@\${fn}
                        cp \${fn} staging/rh-acs/${params.REPO}@\${fn}
                        mkdir -p staging/rhacs/${params.REPO}
                        mkdir -p staging/rh-acs/${params.REPO}
                        scp -r -o StrictHostKeychecking=no staging/* ${mirrorTarget}:/srv/pub/rhacs/signatures/
                        """
                        mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", 'rhacs/signatures')
                        if (mirror_result.contains("[FAILURE]")) {
                            echo mirror_result
                            error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                        }
                    }
                } finally {
                    echo "Archiving artifacts in jenkins:"
                    commonlib.safeArchiveArtifacts([
                        "working/cp.log",
                        "working/*.gpg",
                        "working/sha256=*",
                        ]
                    )
                }
            }
        }
    }

    stage('log sync'){
        buildArtifactPath = env.WORKSPACE.replaceFirst('/working/', '/builds/')
        echo "Artifact path (source to sync): ${buildArtifactPath}"
        // Find tool configuration for 'rclone' in bitwarden under
        // "ART S3 Signing Job Logs Bucket"
        //
        // Non-Obvious Option Notes:
        //   --no-traverse=Don't traverse destination file system on
        //       copy. We have a lot of files remotely, so this should
        //       speed things up.
        //   --max-age=Consider local items modified within the period given
        //   --low-level-retries 1=Don't bother retrying small
        //       failures, just do full retries
        //   --local-no-check-updated=The log we are copying for this
        //       job is constantly updating, it's ok, don't worry
        //       about it. We'll update the remote version next time
        //   --ignore-existing=We can't update s3 objects, so don't
        //       consider for syncing if they are already on the remote
        def logCopyOpts = "--verbose copy --s3-chunk-size 5M --exclude 'program.dat' --no-traverse --max-age 24h --retries-sleep 10s --ignore-existing --local-no-check-updated --low-level-retries 1 --retries 5 ${buildArtifactPath} s3SigningLogs:art-build-artifacts/signing-jobs/signing%2Fsign-artifacts/"

	sh "/bin/rclone version"

        if ( !params.DRY_RUN ) {
            sh "/bin/rclone ${logCopyOpts}"
        } else {
            echo "DRY-RUN, not syncing logs (but this would have happened):"
            echo "Artifact path (source to sync): ${buildArtifactPath}"
            sh "/bin/rclone --dry-run ${logCopyOpts}"
        }
    }

    buildlib.cleanWorkspace()
}

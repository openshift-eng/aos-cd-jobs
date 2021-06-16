#!/usr/bin/env groovy

node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("sign-artifacts", """
        <h2>Sign OCP4 release image / clients and publish signatures</h2>
        <b>Timing</b>: The "release" job runs this after a release is accepted.
        Can be run manually if that fails.

        See https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#sign-the-release

        The shasum file for the clients is signed and signatures published next
        to the shasum file itself.
            http://mirror.openshift.com/pub/openshift-v4/<arch>/clients/ocp/
        The release image shasum is signed and the signature published both on
        Google Cloud Storage and mirror:
            <a href="http://mirror.openshift.com/pub/openshift-v4/signatures/openshift/" target="_blank">http://mirror.openshift.com/pub/openshift-v4/signatures/openshift/</a>
    """)


    // Expose properties for a parameterized build
    properties(
        [
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    choice(
                        name: 'ARCH',
                        description: 'The architecture for this release',
                        choices: [
                            "x86_64",
                            "s390x",
                            "ppc64le",
                            "aarch64",
                        ].join("\n"),
                    ),
                    string(
                        name: 'NAME',
                        description: 'Release name (e.g. 4.2.0)',
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
                        name: 'CLIENT_TYPE',
                        description: 'Which type is it, stable (ocp) or dev (ocp-dev-preview)?',
                        choices: [
                            "ocp",
                            "ocp-dev-preview",
                        ].join("\n"),
                    ),
                    choice(
                        name: 'PRODUCT',
                        description: 'Which product to sign',
                        choices: [
                            "openshift",
                            "rhcos",
                            "rhacs",
                        ].join("\n"),
                    ),
                    choice(
                        name: 'ENV',
                        description: 'Which environment to sign in',
                        choices: [
                            "stage",
                            "prod",
                        ].join("\n"),
                    ),
                    choice(
                        name: 'KEY_NAME',
                        description: 'Which key to sign with\nIf ENV==stage everything becomes "test"\nFor prod we currently use "redhatrelease2"',
                        choices: [
                            "test",
                            "beta2",
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

        currentBuild.displayName += "- ${params.NAME}"
        if (params.DRY_RUN) {
            currentBuild.displayName += " (dry-run)"
            currentBuild.description = "[DRY RUN]"
        }

        if ( !env.JOB_NAME.startsWith("signing-jobs/") ) {
            requestIdSuffix = "-test"
        } else {
            requestIdSuffix = ""
        }

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
                                --release-name "${params.NAME}" --client-cert ${busCertificate}
                                --client-key ${busKey} --env ${params.ENV}
                            """)

                    if ( params.PRODUCT == 'openshift' ) {
                        // ######################################################################
                        // Does the required sha256sum.txt file exist yet?
                        def shaFile = "https://mirror.openshift.com/pub/openshift-v4/${params.ARCH}/clients/${params.CLIENT_TYPE}/${params.NAME}/sha256sum.txt"
                        try {
                            echo("Checking if required sha256sum.txt file exists")
                            httpRequest(
                                httpMode: 'HEAD',
                                responseHandle: 'NONE',
                                url: shaFile,
                            )
                        } catch (exc) {
                            echo("ERROR: Required sha256sum.txt file is missing")
                            currentBuild.description += "\nCould not submit OpenShift signing requests, the required sha256sum.txt file is missing"
                            error("Expected to find: ${shaFile} but it was missing")
                        }

                        def openshiftJsonSignParams = buildlib.cleanWhitespace("""
                             ${baseUmbParams} --product openshift --arch ${params.ARCH} --client-type ${params.CLIENT_TYPE}
                             --request-id 'openshift-json-digest-${env.BUILD_ID}${requestIdSuffix}' ${digestParam} ${noop}
                         """)

                        echo "Submitting OpenShift Payload JSON claim signature request"
                        retry(3) {
                            timeout(time: 3, unit: 'MINUTES') {
                                commonlib.shell(
                                    script: "../umb_producer.py json-digest ${openshiftJsonSignParams}"
                                )
                            }
                        }

                        // ######################################################################

                        def openshiftSha256SignParams = buildlib.cleanWhitespace("""
                            ${baseUmbParams} --product openshift --arch ${params.ARCH} --client-type ${params.CLIENT_TYPE}
                            --request-id 'openshift-message-digest-${env.BUILD_ID}${requestIdSuffix}' ${noop}
                        """)

                        echo "Submitting OpenShift sha256 message-digest signature request"
                        retry(3) {
                            timeout(time: 3, unit: 'MINUTES') {
                                commonlib.shell(
                                    script: "../umb_producer.py message-digest ${openshiftSha256SignParams}"
                                )
                            }
                        }
                    } else if ( params.PRODUCT == 'rhcos' ) {
                        def rhcosSha256SignParams = buildlib.cleanWhitespace("""
                            ${baseUmbParams} --product rhcos ${noop} --arch ${params.ARCH}
                            --request-id 'rhcos-message-digest-${env.BUILD_ID}${requestIdSuffix}'
                        """)

                        echo "Submitting RHCOS sha256 message-digest signature request"
                        retry(3) {
                            timeout(time: 3, unit: 'MINUTES') {
                                res = commonlib.shell(
                                    returnAll: true,
                                    script: "../umb_producer.py message-digest ${rhcosSha256SignParams}"
                                )
                            }
                        }
                    } else if ( params.PRODUCT == 'rhacs' ) {
                        def openshiftJsonSignParams = buildlib.cleanWhitespace("""
                             ${baseUmbParams} --product openshift --arch ${params.ARCH} --client-type ${params.CLIENT_TYPE}
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
    }

    stage('mirror artifacts') {
        // This job mirrors two different kinds of signatures.
        //
        // 1) JSON digest claims, they are signatures for the release
        // payload, stored in a JSON format.
        //
        // 2) Message digests, they are sha256sum.txt files which have
        // sha digests for a directory of contents
        // ######################################################################

        mirrorTarget = "use-mirror-upload.ops.rhcloud.com"
        if (params.DRY_RUN) {
            echo "Would have archived artifacts in jenkins"
            echo "Would have mirrored artifacts to mirror.openshift.com/pub/:"
            echo "    invoke_on_use_mirror push.pub.sh MIRROR_PATH"
        } else {
            echo "Mirroring artifacts to mirror.openshift.com/pub/"

            dir(workDir) {
                try {
                    if ( params.PRODUCT == 'openshift' ) {
                        // ######################################################################

                        // the umb producer script should have generated two
                        // files. One is a 'sha26=.......' and one is
                        // 'sha256sum.txt.gpg'

                        // sha256=...........
                        //
                        // 1) JSON digest claims. They get mirrored to
                        // mirror.openshift.com/pub/openshift-v4/ using this directory
                        // structure:
                        //
                        // signatures/openshift/release/
                        //   -> sha256=<IMAGE-DIGEST>/signature-1
                        //
                        // where <IMAGE-DIGEST> is the digest of the payload image and
                        // the signed artifact is 'signature-1'
                        //
                        // 2) A message digest (sha256sum.txt) is mirrored to
                        // https://mirror.openshift.com/pub/openshift-v4/clients/
                        // using this directory structure:
                        //
                        // ocp/
                        //  -> <RELEASE-NAME>/sha256sum.txt.gpg
                        //
                        // where <RELEASE-NAME> is something like '4.1.0-rc.5'

                        // transform the file into a directory containing the
                        // file, mirror to google.
                        //
                        // Notes on gsutil options:
                        // -n - no clobber/overwrite
                        // -v - print url of item
                        // -L - write to log for auto re-processing
                        // -r - recursive
                        def googleStoragePath = (params.ENV == 'stage') ? 'test-1' : 'official'
                        def gsutil = '/mnt/nfs/home/jenkins/google-cloud-sdk/bin/gsutil'  // doesn't seem to be in path
                        commonlib.shell("""
                        for file in sha256=*; do
                            mv \$file ${params.SIGNATURE_NAME}
                            mkdir \$file
                            mv ${params.SIGNATURE_NAME} \$file
                            i=1
                            until ${gsutil} cp -n -v -L cp.log -r \$file gs://openshift-release/${googleStoragePath}/signatures/openshift/release; do
                                sleep 1
                                i=\$(( \$i + 1 ))
                                if [ \$i -eq 10 ]; then echo "Failed to mirror to google after 10 attempts. Giving up."; exit 1; fi
                            done
                            until ${gsutil} cp -n -v -L cp.log -r \$file gs://openshift-release/${googleStoragePath}/signatures/openshift-release-dev/ocp-release; do
                                sleep 1
                                i=\$(( \$i + 1 ))
                                if [ \$i -eq 10 ]; then echo "Failed to mirror to google after 10 attempts. Giving up."; exit 1; fi
                            done
                            until ${gsutil} cp -n -v -L cp.log -r \$file gs://openshift-release/${googleStoragePath}/signatures/openshift-release-dev/ocp-release-nightly; do
                                sleep 1
                                i=\$(( \$i + 1 ))
                                if [ \$i -eq 10 ]; then echo "Failed to mirror to google after 10 attempts. Giving up."; exit 1; fi
                            done
                        done
                        """)
                        sshagent(["openshift-bot"]) {
                            def mirrorReleasePath = (params.ENV == 'stage') ? 'test' : 'release'
                            sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256=* ${mirrorTarget}:/srv/pub/openshift-v4/signatures/openshift/${mirrorReleasePath}/"
                            if (mirrorReleasePath == 'release') {
                                sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256=* ${mirrorTarget}:/srv/pub/openshift-v4/signatures/openshift-release-dev/ocp-release/"
                                sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256=* ${mirrorTarget}:/srv/pub/openshift-v4/signatures/openshift-release-dev/ocp-release-nightly/"
                            }
                            mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", 'openshift-v4/signatures')
                            if (mirror_result.contains("[FAILURE]")) {
                                echo mirror_result
                                error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                            }
                        }

                        // ######################################################################

                        // sha256sum.txt.gpg
                        //
                        // For message digests (mirroring type 2) we'll see instead
                        // that .artifact_meta.type says 'message-digest'. Take this
                        // for example (request to sign the sha256sum.txt file from
                        // 4.1.0-rc.5):
                        //
                        //     "artifact_meta": {
                        //         "product": "openshift",
                        //         "release_name": "4.1.0-rc.5",
                        //         "type": "message-digest",
                        //         "name": "sha256sum.txt.gpg"
                        //     }
                        //
                        // Note that the 'product' key WILL become important when we
                        // are sending RHCOS bare metal message-digests in the
                        // future. From the .artifact_meta above we know that we have
                        // just received the sha256sum.txt.gpg file for openshift
                        // release 4.1.0-rc.5. We will mirror this file to:
                        //
                        // https://mirror.openshift.com/pub/openshift-v4/clients/
                        //  --> ocp/
                        //  ----> `.artifacts.name`/
                        //  ------> sha256sum.txt.gpg
                        //  ==> https://mirror.openshift.com/pub/openshift-v4/clients/ocp/4.1.0-rc.5/sha256sum.txt.gpg

                        sshagent(["openshift-bot"]) {
                            def mirrorReleasePath = "openshift-v4/${params.ARCH}/clients/${params.CLIENT_TYPE}/${params.NAME}"
                            sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256sum.txt.gpg ${mirrorTarget}:/srv/pub/${mirrorReleasePath}/sha256sum.txt.gpg"
                            mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", mirrorReleasePath)
                            if (mirror_result.contains("[FAILURE]")) {
                                echo mirror_result
                                error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                            }
                        }
                    } else if ( params.PRODUCT == 'rhcos') {
                        sshagent(["openshift-bot"]) {
                            def name_parts = params.NAME.split('\\.')
                            def nameXY = "${name_parts[0]}.${name_parts[1]}"
                            def mirrorReleasePath = "openshift-v4/${params.ARCH}/dependencies/rhcos/${nameXY}/${params.NAME}"
                            sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256sum.txt.gpg ${mirrorTarget}:/srv/pub/${mirrorReleasePath}/sha256sum.txt.gpg"
                            mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", mirrorReleasePath)
                            if (mirror_result.contains("[FAILURE]")) {
                                echo mirror_result
                                error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                            }
                        }
                    } else if ( params.PRODUCT == 'rhacs' ) {
                        sshagent(["openshift-bot"]) {
                            sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256=* ${mirrorTarget}:/srv/pub/rhacs/signatures/rhacs"
                            sh "rsync -avzh -e \"ssh -o StrictHostKeyChecking=no\" sha256=* ${mirrorTarget}:/srv/pub/rhacs/signatures/rh-acs"
                            mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", 'rhacs/signatures')
                            if (mirror_result.contains("[FAILURE]")) {
                                echo mirror_result
                                error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
                            }
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

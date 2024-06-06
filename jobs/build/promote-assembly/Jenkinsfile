#!/usr/bin/env groovy

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("promote-assembly", """
        <h2>Publish official OCP 4 release artifacts</h2>
        <b>Timing</b>: <a href="https://github.com/openshift/art-docs/blob/master/4.y.z-stream.md#create-the-release-image" target="_blank">4.y z-stream doc</a>

        Be aware that by default the job stops for user input very early on. It
        sends slack alerts in our release channels when this occurs.

        For more details see the <a href="https://github.com/openshift-eng/aos-cd-jobs/blob/master/jobs/build/promote/README.md" target="_blank">README</a>
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
                    commonlib.ocpVersionParam('VERSION', '4'),  // not used by "stream" assembly
                    commonlib.artToolsParam(),
                    string(
                        name: 'ASSEMBLY',
                        description: 'The name of an assembly to promote.',
                        defaultValue: "stream",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'NO_MULTI',
                        description: 'Do not promote a multi-arch/heterogeneous payload.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'MULTI_ONLY',
                        description: 'Do not promote arch-specific homogenous payloads.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_MIRROR_BINARIES',
                        description: 'Do not mirror binaries. Useful in case of reruns on subsequent failure',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_CINCINNATI_PR_CREATION',
                        description: 'DO NOT USE without team lead approval. This is an unusual option.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_OTA_SLACK_NOTIFICATION',
                        description: 'Do not notify OTA team in slack for new PRs',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_BUILD_MICROSHIFT',
                        description: 'Do not trigger build-microshift job',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_IMAGE_LIST',
                        description: '(Standard Release) Do not gather an advisory image list for docs.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_ATTACHED_BUG_CHECK',
                        description: 'Skip attached bug check',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_SIGNING',
                        description: 'Do not sign the release (legacy).',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'SKIP_SIGSTORE',
                        description: 'Do not sign the release with the newer sigstore method.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'FORCE_RHCOS_SYNC',
                        description: '(Standard Release) Always sync RHCOS images to mirrors.',
                        defaultValue: false,
                    ),
                    string(
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-art-automation+new-release@redhat.com',
                        ].join(','),
                        trim: true,
                    ),
                    commonlib.dryrunParam('Take no actions. Note: still notifies and runs signing job (which fails)'),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.VERSION)
    def skipAttachedBugCheck = params.SKIP_ATTACHED_BUG_CHECK
    def next_minor = "${major}.${minor + 1}"
    if (params.DRY_RUN) {
        currentBuild.displayName += " (dry-run)"
        currentBuild.description += " [DRY RUN]"
    }
    currentBuild.displayName += " ${params.VERSION} - ${params.ASSEMBLY}"

    stage("Initialize") {
        // Install pyartcd
        commonlib.shell(script: "pip install -e ./art-tools/pyartcd")
        // must be able to access remote registry for verification
        buildlib.registry_quay_dev_login()
    }

    // release_info is the output of `artcd promote` command.
    // It is a dict containing the information of the promoted release.
    // e.g. {"group": "openshift-4.8", "assembly": "4.8.28", "type": "standard", "name": "4.8.28", "content": {"s390x": {"pullspec": "quay.io/openshift-release-dev/ocp-release:4.8.28-s390x", "digest": "sha256:b33d11a797022f9394aca5f05f1fcba8faa3fcc607f0cdd6e75666f8f93e7141", "from_release": "registry.ci.openshift.org/ocp-s390x/release-s390x:4.8.0-0.nightly-s390x-2022-01-19-035735", "rhcos_version": "48.84.202201111102-0"}, "x86_64": {"pullspec": "quay.io/openshift-release-dev/ocp-release:4.8.28-x86_64", "digest": "sha256:ba1299680b542e46744307afc7effc15957a20592d88de4651610b52ed8be9a8", "from_release": "registry.ci.openshift.org/ocp/release:4.8.0-0.nightly-2022-01-19-035759", "rhcos_version": "48.84.202201102304-0"}, "ppc64le": {"pullspec": "quay.io/openshift-release-dev/ocp-release:4.8.28-ppc64le", "digest": "sha256:791790c88018eb9848765797f4348d4d5161dc342c61ec67d41770873e574a43", "from_release": "registry.ci.openshift.org/ocp-ppc64le/release-ppc64le:4.8.0-0.nightly-ppc64le-2022-01-19-035729", "rhcos_version": "48.84.202201102304-0"}}, "justifications": [], "advisory": 87060, "live_url": "https://access.redhat.com/errata/RHBA-2022:0172"}
    def release_info = [:]

    stage("promote release") {
        sh "rm -rf ./artcd_working && mkdir -p ./artcd_working"
        def cmd = [
            "artcd",
            "-v",
            "--working-dir=./artcd_working",
            "--config=./config/artcd.toml",
        ]
        if (params.DRY_RUN) {
            cmd << "--dry-run"
        }
        cmd += [
            "promote",
            "--group=openshift-${params.VERSION}",
            "--assembly=${params.ASSEMBLY}",
        ]
        if (skipAttachedBugCheck) {
            cmd << "--skip-attached-bug-check"
        }
        if (params.SKIP_IMAGE_LIST) {
            cmd << "--skip-image-list"
        }
        if (params.SKIP_BUILD_MICROSHIFT) {
            cmd << "--skip-build-microshift"
        }
        if (params.SKIP_MIRROR_BINARIES) {
            cmd << "--skip-mirror-binaries"
        }
        if (params.SKIP_SIGNING) {
            cmd << "--skip-signing"
        }
        if (params.SKIP_SIGSTORE) {
            cmd << "--skip-sigstore"
        }
        if (params.SKIP_CINCINNATI_PR_CREATION) {
            cmd << "--skip-cincinnati-prs"
        }
        if (params.SKIP_OTA_SLACK_NOTIFICATION) {
            cmd << "--skip-ota-notification"
        }
        if (params.NO_MULTI) {
            cmd << "--no-multi"
        }
        if (params.MULTI_ONLY) {
            cmd << "--multi-only"
        }
        if (major == 4 && minor <= 11) {
            // Add '-multi' to heterogeneous payload name to workaround a Cincinnati issue (#incident-cincinnati-sha-mismatch-for-multi-images).
            // This is also required for 4.11 to prevent the heterogeneous payload from getting into Cincinnati channels
            // because 4.11 heterogeneous is tech preview.
            cmd << "--use-multi-hack"
        }
        def signing_env = params.DRY_RUN? "stage": "prod"
        cmd << "--signing-env=${signing_env}"
        echo "Will run ${cmd}"
        def siging_cert_id = signing_env == "prod" ? "0xffe138e-openshift-art-bot" : "0xffe138d-nonprod-openshift-art-bot"
        def sigstore_creds_file = signing_env == "prod" ? "kms_prod_release_signing_creds_file" : "kms_stage_release_signing_creds_file"
        def sigstore_key_id = signing_env == "prod" ? "kms_prod_release_signing_key_id" : "kms_stage_release_signing_key_id"
        buildlib.withAppCiAsArtPublish() {
            withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'creds_dev_registry.quay.io', usernameVariable: 'QUAY_USERNAME', passwordVariable: 'QUAY_PASSWORD'],
                             aws(credentialsId: 's3-art-srv-enterprise', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'),
                             string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN'),
                             string(credentialsId: 'jboss-jira-token', variable: 'JIRA_TOKEN'),
                             string(credentialsId: 'jenkins-service-account', variable: 'JENKINS_SERVICE_ACCOUNT'),
                             string(credentialsId: 'jenkins-service-account-token', variable: 'JENKINS_SERVICE_ACCOUNT_TOKEN'),
                             string(credentialsId: 'openshift-bot-token', variable: 'GITHUB_TOKEN'),
                             file(credentialsId: "${siging_cert_id}.crt", variable: 'SIGNING_CERT'),
                             file(credentialsId: "${siging_cert_id}.key", variable: 'SIGNING_KEY'),
                             file(credentialsId: sigstore_creds_file, variable: 'KMS_CRED_FILE'),
                             string(credentialsId: sigstore_key_id, variable: 'KMS_KEY_ID'),
                             string(credentialsId: 'redis-server-password', variable: 'REDIS_SERVER_PASSWORD'),
                             string(credentialsId: 'redis-host', variable: 'REDIS_HOST'),
                             string(credentialsId: 'redis-port', variable: 'REDIS_PORT'),
                             file(credentialsId: "art-cluster-art-cd-pipeline-kubeconfig", variable: 'ART_CLUSTER_ART_CD_PIPELINE_KUBECONFIG'),
                            ]) {
                withEnv(["BUILD_URL=${BUILD_URL}"]) {
                    def out = sh(script: cmd.join(' '), returnStdout: true).trim()
                    echo "artcd returns:\n$out"
                    try {
                        release_info = readJSON(text: out)
                    } catch (ex1) {
                        // retry since this is often flaky
                        try {
                            release_info = readJSON(text: out)
                        } catch (ex2) {
                            slacklib.to(params.VERSION).say("@release-artists Promote failed since it couldn't parse pyartcd json. Please investigate/retry")
                            throw ex2
                        }
                    }
                }
            }
        }
    }

    // QE has stop consuming ART's umb events, we can try to stop sending umb event unless someone complains
    // buildlib.registry_quay_dev_login()  // chances are, earlier auth has expired

    // def justifications =release_info.justifications ?: []

    // stage("send release message") {
    //     if (release_info.type == "custom") {
    //         echo "Don't send release messages for a custom release."
    //         return
    //     }
    //     if (params.DRY_RUN) {
    //         echo "DRY_RUN: Would have sent release messages."
    //         return
    //     }

    //     List<String> umb_failures = []
    //     release_info.content.each { arch, info ->
    //         // Currently a multi/heterogeneous release payload has a modified release name to workaround a Cincinnati issue.
    //         // Using the real per-arch release name in $info instead of the one defined by release artists.
    //         def release_name = info.metadata.version
    //         try {
    //             release.sendReleaseCompleteMessage(["name": release_name], release_info.advisory ?: 0, release_info.live_url, arch)
    //         } catch (exception) {
    //             umb_failures.add("${release_name}-${arch}")
    //         }
    //     }
    //     if (umb_failures) {
    //         currentBuild.result = "UNSTABLE"
    //         slacklib.to(params.VERSION).say("@release-artists Sending Release Complete informational message has failed for ${umb_failures}, please investigate")
    //     }
    // }

    stage("clean and mail") {
        dry_subject = ""
        if (params.DRY_RUN) { dry_subject = "[DRY RUN] "}
        def pullspecs = release_info.content.findAll{ k, v -> v.pullspec }.collect {k, v -> v.pullspec }
        commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "${dry_subject}Success building release payload: ${release_info.name}",
            body: """
Jenkins Job: ${env.BUILD_URL}
PullSpecs: ${pullspecs.join(",")}
        """);
        buildlib.cleanWorkspace()
    }

}

#!/usr/bin/env groovy
import groovy.transform.Field

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    def slacklib = commonlib.slacklib
    def quay_url = "quay.io/openshift-release-dev/ocp-release"

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
                    [
                        name: 'FROM_RELEASE_TAG',
                        description: 'Build tag to pull from (e.g. 4.1.0-0.nightly-2019-04-22-005054)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'NAME',
                        description: 'Release name (e.g. 4.1.0)',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'DESCRIPTION',
                        description: 'Should be empty unless you know otherwise',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'ADVISORY',
                        description: 'Optional: Image release advisory number. If not given, the number will be retrived from ocp-build-data.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'PREVIOUS',
                        description: 'Check item #6 "PREVIOUS" of the following doc for instructions on how to fill this field:\nhttps://mojo.redhat.com/docs/DOC-1201843#jive_content_id_Completing_a_4yz_release',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: ""
                    ],
                    [
                        name: 'PERMIT_PAYLOAD_OVERWRITE',
                        description: 'DO NOT USE without team lead approval. Allows the pipeline to overwrite an existing payload in quay.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'PERMIT_ALL_ADVISORY_STATES',
                        description: 'DO NOT USE without team lead approval. Allows release job to run when advisory is not in QE state.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'SKIP_IMAGE_LIST',
                        description: 'Do not gather an advisory image list for docs. Use this for RCs and other test situations.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'DRY_RUN',
                        description: 'Only do dry run test and exit.',
                        $class: 'BooleanParameterDefinition',
                        defaultValue: false
                    ],
                    [
                        name: 'MAIL_LIST_SUCCESS',
                        description: 'Success Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-cicd@redhat.com',
                            'aos-qe@redhat.com',
                            'aos-team-art@redhat.com',
                            'aos-art-automation+new-release@redhat.com',
                        ].join(',')
                    ],
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: [
                            'aos-art-automation+failed-release@redhat.com'
                        ].join(',')
                    ],
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    buildlib.cleanWorkdir("${env.WORKSPACE}")

    slackChannel = slacklib.to(FROM_RELEASE_TAG)
    slackChannel.task("Public release prep for: ${FROM_RELEASE_TAG}") {
        taskThread ->
        sshagent(['aos-cd-test']) {
            release_info = ""
            release_name = params.NAME.trim()
            from_release_tag = params.FROM_RELEASE_TAG.trim()
            arch = release.getReleaseTagArch(from_release_tag)
            archSuffix = release.getArchSuffix(arch)
            RELEASE_STREAM_NAME = "4-stable${archSuffix}"
            dest_release_tag = release.destReleaseTag(release_name, arch)


            description = params.DESCRIPTION
            advisory = params.ADVISORY ? Integer.parseInt(params.ADVISORY.toString()) : 0
            previous = params.PREVIOUS
            String errata_url
            Map release_obj
            def CLIENT_TYPE = 'ocp'


            currentBuild.displayName += "- ${name}"
            if (params.DRY_RUN) {
                currentBuild.displayName += " (dry-run)"
                currentBuild.description += "[DRY RUN]"
            }


            // must be able to access remote registry for verification
            buildlib.registry_quay_dev_login()
            stage("versions") { release.stageVersions() }
            stage("validation") {
                def retval = release.stageValidation(quay_url, dest_release_tag, advisory, params.PERMIT_PAYLOAD_OVERWRITE, params.PERMIT_ALL_ADVISORY_STATES)
                advisory = advisory?:retval.advisoryInfo.id
                errata_url = retval.errataUrl
            }
            stage("build payload") { release.stageGenPayload(quay_url, release_name, dest_release_tag, from_release_tag, description, previous, errata_url) }

            stage("tag stable") { release.stageTagRelease(quay_url, release_name, dest_release_tag, arch) }

            stage("request upgrade tests") {
                def (major,minor) = extractMajorMinorVersion(NAME)
                def previousList = PREVIOUS.trim().tokenize('\t ,')
                def modeOptions = [ 'aws', 'gcp', 'azure,mirror' ]
                if ( major == '4' && minor == '1') {
                    modeOptions = ['aws'] // gcp and azure were not supported in 4.1
                }
                def testIndex = 0
                def testLines = []
                for ( String from_release : previousList) {
                    mode = modeOptions[testIndex % modeOptions.size()]
                    testLines << "test upgrade ${from_release} ${NAME} ${mode}"
                    testIndex++
                }
                try {  // don't let a slack outage break the job
                    def slackChannel = slacklib.to('#team-art')
                    slackChannel.say("Hi @release-artists . A new release is ready and needs some upgrade tests to be triggered. "
                        + "Please open a chat with @cluster-bot and issue each of these lines individually:\n${testLines.join('\n')}")
                } catch(ex) {
                    echo "slack notification failed: ${ex}"
                }
                currentBuild.description += "\n@cluster-bot requests:\n${testLines.join('\n')}\n"
            }

            stage("wait for stable") {
                commonlib.retrySkipAbort("Waiting for stable ${release_name}",
                                        "Release ${release_name} is not currently Accepted by release controller. Issue cluster-bot requests for each upgrade test. "
                                         + "SKIP when at least one test passes for each upgrade type. Or RETRY if the release is finally Accepted.",
                                         taskThread)  {
                    release_obj = release.stageWaitForStable(RELEASE_STREAM_NAME, release_name)
                 }
            }

            stage("get release info") {
                release_info = release.stageGetReleaseInfo(quay_url, dest_release_tag)
            }

            stage("advisory image list") {
                if (env.SKIP_IMAGE_LIST) {
                    currentBuild.description += "[No image list]"
                    return
                }
                try {
                    filename = "${dest_release_tag}-image-list.txt"
                    retry (3) {
                        commonlib.shell(script: "elliott advisory-images -a ${advisory} > ${filename}")
                    }
                    archiveArtifacts(artifacts: filename, fingerprint: true)
                    if (!env.DRY_RUN) {
                        commonlib.email(
                            to: "openshift-ccs@redhat.com",
                            cc: "aos-team-art@redhat.com",
                            replyTo: "aos-team-art@redhat.com",
                            subject: "OCP ${release_name} (${arch}) Image List",
                            body: readFile(filename)
                        )
                    }
                } catch (ex) {
                    currentBuild.description += "Image list failed. Marked UNSTABLE and continuing."
                    currentBuild.result = "UNSTABLE"
                }
            }

            buildlib.registry_quay_dev_login()  // chances are, earlier auth has expired
            stage("mirror tools") { 
              retry(3) {
                release.stagePublishClient(quay_url, dest_release_tag, release_name, arch, CLIENT_TYPE)
              }
            }
            stage("advisory update") { release.stageAdvisoryUpdate() }
            stage("cross ref check") { release.stageCrossRef() }
            stage("send release message") { release.sendReleaseCompleteMessage(release_obj, advisory, errata_url, arch) }
            stage("sign artifacts") {
                commonlib.retrySkipAbort("Signing artifacts", "Error running signing job", taskThread) {
                    release.signArtifacts(
                        name: name,
                        signature_name: "signature-1",
                        dry_run: params.DRY_RUN,
                        env: "prod",
                        key_name: "redhatrelease2",
                        arch: arch,
                        digest: payloadDigest,
                        client_type: "ocp",
                    )
                }
            }

            stage("channel prs") {
                release.openCincinnatiPRs(NAME, errata_url)
            }

        }

        dry_subject = ""
        if (params.DRY_RUN) { dry_subject = "[DRY RUN] "}

        commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "${dry_subject}Success building release payload: ${release_name} (${arch})",
            body: """
Jenkins Job: ${env.BUILD_URL}
Release Page: https://openshift-release${archSuffix}.svc.ci.openshift.org/releasestream/4-stable${archSuffix}/release/${release_name}
Quay PullSpec: quay.io/openshift-release-dev/ocp-release:${dest_release_tag}

${release_info}
        """);
    }
}

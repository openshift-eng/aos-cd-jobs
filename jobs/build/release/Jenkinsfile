#!/usr/bin/env groovy
import groovy.transform.Field

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def slacklib = load("pipeline-scripts/slacklib.groovy")
    def buildlib = release.buildlib
    def commonlib = release.commonlib
    def quay_url = "quay.io/openshift-release-dev/ocp-release"

    // Expose properties for a parameterized build
    properties(
        [
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

    jobThread = slacklib.to(FROM_RELEASE_TAG)
    jobThread.task("Public release prep for: ${FROM_RELEASE_TAG}") {
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
            stage("wait for stable") { release_obj = release.stageWaitForStable(RELEASE_STREAM_NAME, release_name) }
            stage("get release info") {
                release_info = release.stageGetReleaseInfo(quay_url, dest_release_tag)
            }
            stage("advisory image list") {
                filename = "${dest_release_tag}-image-list.txt"
                retry (3) {
                    commonlib.shell(script: "elliott advisory-images -a ${advisory} > ${filename}")
                }
                archiveArtifacts(artifacts: filename, fingerprint: true)
                commonlib.email(
                    to: "openshift-ccs@redhat.com",
                    cc: "aos-team-art@redhat.com",
                    replyTo: "aos-team-art@redhat.com",
                    subject: "OCP ${release_name} (${arch}) Image List",
                    body: readFile(filename)
                )
            }
            buildlib.registry_quay_dev_login()  // chances are, earlier auth has expired
            stage("mirror tools") { release.stagePublishClient(quay_url, dest_release_tag, release_name, arch, CLIENT_TYPE) }
            stage("advisory update") { release.stageAdvisoryUpdate() }
            stage("cross ref check") { release.stageCrossRef() }
            stage("send release message") { release.sendReleaseCompleteMessage(release_obj, advisory, errata_url, arch) }
            stage("sign artifacts") {
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

#!/usr/bin/env groovy
import groovy.transform.Field

node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
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
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()

    buildlib.cleanWorkdir("${env.WORKSPACE}")

    try {
        sshagent(['aos-cd-test']) {
            release_info = ""
            def dest_release_tag = "${params.NAME}"
            arch = release.getReleaseTagArch(params.FROM_RELEASE_TAG)
            archSuffix = ''
            if ( arch != 'x86_64' ) {
                archSuffix = "-${arch}"
            }
            RELEASE_STREAM_NAME = "4-stable${archSuffix}"


            from_release_tag = "${params.FROM_RELEASE_TAG}"
            description = "${params.DESCRIPTION}"
            advisory = params.ADVISORY? Integer.parseInt(params.ADVISORY.toString()) : 0
            previous = "${params.PREVIOUS}"
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
                def retval = release.stageValidation(quay_url, dest_release_tag, advisory)
                advisory = advisory?:retval.advisoryInfo.id
                errata_url = retval.errataUrl
            }
            stage("build payload") { release.stageGenPayload(quay_url, dest_release_tag, from_release_tag, description, previous, errata_url) }
            stage("tag stable") { release.stageTagRelease(quay_url, dest_release_tag) }
            stage("wait for stable") { release_obj = release.stageWaitForStable(RELEASE_STREAM_NAME, dest_release_tag) }
            stage("get release info") {
                release_info = release.stageGetReleaseInfo(quay_url, dest_release_tag)
            }
            stage("advisory image list") {
                filename = "${params.NAME}-image-list.txt"
                retry (3) {
                    commonlib.shell(script: "elliott advisory-images -a ${advisory} > ${filename}")
                }
                archiveArtifacts(artifacts: filename, fingerprint: true)
                commonlib.email(
                    to: "openshift-ccs@redhat.com",
                    cc: "aos-team-art@redhat.com",
                    replyTo: "aos-team-art@redhat.com",
                    subject: "OCP ${params.NAME} Image List",
                    body: readFile(filename)
                )
            }
            buildlib.registry_quay_dev_login()  // chances are, earlier auth has expired
            stage("mirror tools") { release.stagePublishClient(quay_url, dest_release_tag, arch, CLIENT_TYPE) }
            stage("advisory update") { release.stageAdvisoryUpdate() }
            stage("cross ref check") { release.stageCrossRef() }
            stage("send release message") { release.sendReleaseCompleteMessage(release_obj, advisory, errata_url) }
            stage("sign artifacts") {
                release.signArtifacts(
                    name: name,
                    signature_name: "signature-1",
                    dry_run: params.DRY_RUN,
                    env: "prod",
                    key_name: "redhatrelease2",
                    arch: arch,
                    digest: payloadDigest,
                )
            }
        }

        dry_subject = ""
        if (params.DRY_RUN) { dry_subject = "[DRY RUN] "}

        commonlib.email(
            to: "${params.MAIL_LIST_SUCCESS}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "${dry_subject}Success building release payload: ${params.NAME}",
            body: """
Jenkins Job: ${env.BUILD_URL}
Release Page: https://openshift-release${archSuffix}.svc.ci.openshift.org/releasestream/4-stable${archSuffix}/release/${params.NAME}
Quay PullSpec: quay.io/openshift-release-dev/ocp-release:${params.NAME}

${release_info}
        """);
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            replyTo: "aos-team-art@redhat.com",
            from: "aos-art-automation@redhat.com",
            subject: "Error running OCP Release",
            body: "Encountered an error while running OCP release: ${err}");
        currentBuild.description = "Error while running OCP release:\n${err}"
        currentBuild.result = "FAILURE"
        throw err
    }
}

#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def buildlib = build.buildlib
    def commonlib = build.commonlib
    commonlib.describeJob("rhcos_sync", """
        ------------------------------------
        Sync the RHCOS boot images to mirror
        ------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/<arch>/dependencies/rhcos/
        Publishes RHCOS boot images for a particular release so that customers
        can base their OCP 4 installs on them.

        Timing: This is only ever run by humans, usually when a new minor
        version / arch is released. It may also be used when there is a
        boot-time bug requiring updated boot images in a version already
        released.

        See https://mojo.redhat.com/docs/DOC-1216700#jive_content_id_Publish_RHCOS_bootimages
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
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'NAME',
                        description: 'The release name, like 4.2.0, or 4.2.0-0.nightly-2019-08-28-152644',
                        defaultValue: "",
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'Which architecture of RHCOS build to look for',
                        choices: (['x86_64', 's390x', 'ppc64le', 'aarch64']),
                    ),
                    choice(
                        name: 'RHCOS_MIRROR_PREFIX',
                        description: 'Where to place this release under https://mirror.openshift.com/pub/openshift-v4/ARCH/dependencies/rhcos/',
                        choices: (['pre-release', 'test'] + commonlib.ocp4Versions),
                    ),
                    string(
                        name: 'RHCOS_BUILD',
                        description: 'ID of the RHCOS build to sync. e.g.: 42.80.20190828.2',
                        defaultValue: "",
                    ),
                    booleanParam(
                        name: 'DRY_RUN',
                        description: 'Run commands with their dry-run options enabled (test everything)',
                        defaultValue: false,
                    ),
                    string(
                        name: 'SYNC_LIST',
                        description: 'Instead of figuring out items to sync from meta.json, use this input file.\nMust be a URL reachable from buildvm, contents must be reachable from use-mirror-upload',
                        defaultValue: "",
                    ),
                    booleanParam(
                        name: 'FORCE',
                        description: 'Download (overwrite) and mirror items even if the destination directory already exists\nErases everything already in the target destination.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'NO_LATEST',
                        description: 'Do not update the "latest" symlink after downloading',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'NO_MIRROR',
                        description: 'Do not run the push.pub script after downloading',
                        defaultValue: false,
                    ),
                    commonlib.suppressEmailParam(),
                    commonlib.mockParam(),
                ],
            ]
        ]
    )

    commonlib.checkMock()
    echo("Initializing RHCOS-${params.RHCOS_MIRROR_PREFIX} sync: #${currentBuild.number}")
    build.initialize()

    try {
        if ( params.SYNC_LIST == "" ) {
            stage("Get/Generate sync list") { build.rhcosSyncPrintArtifacts() }
        } else {
            stage("Get/Generate sync list") { build.rhcosSyncManualInput() }
        }
        stage("Mirror artifacts") { build.rhcosSyncMirrorArtifacts() }
        // stage("Gen AMI docs") { build.rhcosSyncGenDocs() }
    } catch ( err ) {
        commonlib.email(
            to: "aos-art-automation+failed-rhcos-sync@redhat.com",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error during OCP ${params.RHCOS_MIRROR_PREFIX} build sync",
            body: """
There was an issue running build-sync for OCP ${params.RHCOS_MIRROR_PREFIX}:

    ${err}
""")
        throw ( err )
    } finally {
        commonlib.safeArchiveArtifacts(build.artifacts)
    }
}

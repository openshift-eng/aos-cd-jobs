#!/usr/bin/env groovy

node {
    checkout scm
    def build = load("build.groovy")
    def releaselib = build.releaselib
    def buildlib = build.buildlib
    def commonlib = build.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("rhcos_sync", """
        <h2>Sync the RHCOS boot images to mirror</h2>
        http://mirror.openshift.com/pub/openshift-v4/<arch>/dependencies/rhcos/
        Publishes RHCOS boot images for a particular release so that customers
        can base their OCP 4 installs on them.

        Timing: This is only ever run by humans, usually when a new minor
        version / arch is released. It may also be used when there is a
        boot-time bug requiring updated boot images in a version already
        released.

        See <a href="https://mojo.redhat.com/docs/DOC-1216700#jive_content_id_Publish_RHCOS_bootimages" target="_blank">the docs</a>
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
                    string(
                        name: 'FROM_RELEASE_TAG',
                        description: 'Release Image to get RHCOS buildID from ex - 4.8.2-x86_64 or 4.8.0-0.nightly-2021-07-21-150743',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.ocpVersionParam('OCP_VERSION', '4', ['auto']),
                    string(
                        name: 'OVERRIDE_BUILD',
                        description: 'ID of the RHCOS build to sync. e.g.: 42.80.20190828.2. This overrides FROM_RELEASE_TAG.',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'Which architecture of RHCOS build to look for. Required with OVERRIDE_BUILD',
                        choices: (["auto"] + commonlib.brewArches),
                    ),
                    string(
                        name: 'OVERRIDE_NAME',
                        description: 'The release name, like 4.2.0, or 4.2.0-0.nightly-2019-08-28-152644. Required with OVERRIDE_BUILD',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'MIRROR_PREFIX',
                        description: 'Where to place this release under https://mirror.openshift.com/pub/openshift-v4/ARCH/dependencies/rhcos/. Auto sets to image version for stable releases (example if FROM_RELEASE_TAG is 4.8.4-x86_64 then directory is 4.8), pre-release for all other FROM_RELEASE_TAG values. "auto" cannot be used with OVERRIDE_BUILD',
                        choices: (['auto' ,'pre-release', 'test'] + commonlib.ocp4Versions),
                    ),
                    string(
                        name: 'SYNC_LIST',
                        description: 'Instead of figuring out items to sync from meta.json, use this input file.\nMust be a URL reachable from buildvm, contents must be reachable from use-mirror-upload',
                        defaultValue: "",
                        trim: true,
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
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                ],
            ]
        ]
    )

    commonlib.checkMock()

    if (params.OVERRIDE_BUILD != "") {
        if (params.OVERRIDE_NAME == "") {
            error("Need a valid OVERRIDE_NAME value")
        }
        if (params.ARCH == "auto") {
            error("ARCH cannot be auto, need to be explicit")
        }
        if (params.MIRROR_PREFIX == "auto") {
            error("MIRROR_PREFIX cannot be auto, need to be explicit")
        }
        if (params.OCP_VERSION == "auto") {
            error("OCP_VERSION cannot be auto, need to be explicit")
        }
        ocpVersion = params.OCP_VERSION
        rhcosBuild = params.OVERRIDE_BUILD
        arch = params.ARCH
        name = params.OVERRIDE_NAME
    } else {
        if (!params.FROM_RELEASE_TAG) {
            error("Need FROM_RELEASE_TAG")
        }

        tag = params.FROM_RELEASE_TAG
        if (params.OVERRIDE_NAME != "") {
            name = params.OVERRIDE_NAME
        } else {
            name = tag
        }

        (major, minor) = commonlib.extractMajorMinorVersionNumbers(tag)
        ocpVersion = "$major.$minor"

        (arch, priv) = releaselib.getReleaseTagArchPriv(tag)
        suffix = releaselib.getArchPrivSuffix(arch, priv)

        cmd = "oc image info -o json \$(oc adm release info --image-for machine-os-content registry.ci.openshift.org/ocp$suffix/release$suffix:$tag) | jq -r .config.config.Labels.version"
        rhcosBuild =  commonlib.shell(
            returnStdout: true,
            script: cmd
        ).trim()
    }

    if (params.MIRROR_PREFIX == 'auto') {
        pattern = /$major\.$minor\.(\d+)-$arch/
        is_stable = tag ==~ pattern
        mirrorPrefix = is_stable ? ocpVersion : "pre-release"
    } else {
        mirrorPrefix = params.MIRROR_PREFIX
    }

    print("RHCOS build: $rhcosBuild, arch: $arch, mirror prefix: $mirrorPrefix")

    echo("Initializing RHCOS-${params.MIRROR_PREFIX} sync: #${currentBuild.number}")
    build.initialize(ocpVersion, rhcosBuild, arch, name, mirrorPrefix)

    try {
        if ( params.SYNC_LIST == "" ) {
            stage("Get/Generate sync list") { build.rhcosSyncPrintArtifacts() }
        } else {
            stage("Get/Generate sync list") { build.rhcosSyncManualInput() }
        }
        stage("Mirror artifacts") {
            build.rhcosSyncMirrorArtifacts(mirrorPrefix, arch, rhcosBuild, name)
        }
        // stage("Gen AMI docs") { build.rhcosSyncGenDocs(rhcosBuild) }
        stage("Slack notification to release channel") {
            slacklib.to(ocpVersion).say("""
            *:white_check_mark: rhcos_sync (${mirrorPrefix}) successful*
            https://mirror.openshift.com/pub/openshift-v4/${arch}/dependencies/rhcos/${mirrorPrefix}/${name}/

            buildvm job: ${commonlib.buildURL('console')}
            """)
        }

        // only run for x86_64 since no AMIs for other arches
        // only sync AMI to ROSA Marketplace account when no custom sync list is defined
        if ( params.SYNC_LIST == "" && arch == "x86_64") {
            stage("Mirror ROSA AMIs") {
                if ( arch != 'x86_64' ) {
                    echo "Skipping ROSA sync for non-x86 arch"
                    return
                }
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', accessKeyVariable: 'AWS_ACCESS_KEY_ID', credentialsId: 'artjenkins_rhcos_rosa_marketplace_staging', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                    build.rhcosSyncROSA()
                }
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', accessKeyVariable: 'AWS_ACCESS_KEY_ID', credentialsId: 'artjenkins_rhcos_rosa_marketplace_production', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                    build.rhcosSyncROSA()
                }
            }
            stage("Slack notification to release channel") {
                slacklib.to(ocpVersion).say("""
                *:white_check_mark: rosa_sync (${name}) successful*
                """)
            }
        }
    } catch ( err ) {
        slacklib.to(ocpVersion).say("""
        *:heavy_exclamation_mark: rhcos_sync ${mirrorPrefix} failed*
        buildvm job: ${commonlib.buildURL('console')}
        """)
        commonlib.email(
            to: "aos-art-automation+failed-rhcos-sync@redhat.com",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Error during OCP ${mirrorPrefix} build sync",
            body: """
There was an issue running build-sync for OCP ${mirrorPrefix}:

    ${err}
""")
        throw ( err )
    } finally {
        commonlib.safeArchiveArtifacts(build.artifacts)
        buildlib.cleanWorkspace()
    }
}

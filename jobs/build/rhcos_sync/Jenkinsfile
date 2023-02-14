#!/usr/bin/env groovy

node {
    checkout scm
    def rhcoslib = load("rhcoslib.groovy")
    def releaselib = rhcoslib.releaselib
    def buildlib = rhcoslib.buildlib
    def commonlib = rhcoslib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("rhcos_sync", """
        <h2>Sync the RHCOS boot images to mirror</h2>
        <ul><li>http://mirror.openshift.com/pub/openshift-v4/\$ARCH/dependencies/rhcos/</li></ul>
        Publishes RHCOS boot images for a particular release (according to the
        installer image manifest) so that customers can base their OCP 4
        installs on them. Also updates <code>latest</code> directory by default.

        Timing: This is only ever run by humans, usually when a new minor
        version / arch is released. It may also be used when there is a
        boot-time bug requiring updated boot images in a version already
        released.
        See <a href="https://art-docs.engineering.redhat.com/release/4.y-ga/#publish-rhcos-bootimages" target="_blank">the docs</a>
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
                    string(
                        name: 'FROM_RELEASE_TAG',
                        description: 'Release Name (or pullspec with a tag) from which to get RHCOS buildID reference (ex. 4.12.0-ec.2-x86_64). <b>Note:</b> The buildID is pulled from the installer image in the payload, which is often different from what is in the rhcos image - so make sure the installer image points to the right buildID OR use OVERRIDE_BUILD.',
                        defaultValue: "",
                        trim: true,
                    ),
                    commonlib.ocpVersionParam('OCP_VERSION', '4', ['auto']),
                    string(
                        name: 'OVERRIDE_BUILD',
                        description: 'ID of the RHCOS build to sync. e.g.: <b>42.80.20190828.2</b>. This overrides what would be inferred from <code>FROM_RELEASE_TAG</code> and requires explicit specifications below too.',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'ARCH',
                        description: 'Which architecture of RHCOS build to look for. Required with <code>OVERRIDE_BUILD</code>',
                        choices: (["auto"] + commonlib.brewArches),
                    ),
                    string(
                        name: 'OVERRIDE_NAME',
                        description: 'The release name, like <b>4.2.0</b>, or <b>4.2.0-0.nightly-2019-08-28-152644</b>. Required with <code>OVERRIDE_BUILD</code>',
                        defaultValue: "",
                        trim: true,
                    ),
                    choice(
                        name: 'MIRROR_PREFIX',
                        description: 'Where to place this release under <b><code>https://mirror.openshift.com/pub/openshift-v4/ARCH/dependencies/rhcos/<code></b>. Auto sets to image version for stable releases (example if <code>FROM_RELEASE_TAG</code> is <b>4.8.4-x86_64</b> then directory is <b>4.8</b>), <b>pre-release</b> for all other <code>FROM_RELEASE_TAG</code> values. <b>auto</b> cannot be used with <code>OVERRIDE_BUILD</code>',
                        choices: (['auto' ,'pre-release', 'test'] + commonlib.ocp4Versions),
                    ),
                    string(
                        name: 'SYNC_LIST',
                        description: 'Instead of figuring out items to sync from meta.json, use this input file.<br>Must be a URL reachable from buildvm.<br>If name ends in ".json" then read it like meta.json, otherwise content should be line-separated filenames.',
                        defaultValue: "",
                        trim: true,
                    ),
                    booleanParam(
                        name: 'FORCE',
                        description: 'Download (overwrite) and mirror items even if the destination directory already exists<br>Erases everything already in the target destination.',
                        defaultValue: false,
                    ),
                    booleanParam(
                        name: 'NO_LATEST',
                        description: 'Do not update the <b>latest</b> symlink after downloading',
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
        image = "quay.io/openshift-release-dev/ocp-release:${tag}"
        if (tag.contains("/")) {
            // assume instead of a tag it's a pullspec e.g. to registry.ci
            if (!tag.contains(":")) error("FROM_RELEASE_TAG pullspec must include a :tag")
            image = tag
            tag = tag.split(":")[-1]
        }

        if (params.OVERRIDE_NAME != "")
            name = params.OVERRIDE_NAME
        else
            name = commonlib.shell(
                returnStdout: true,
                script: "oc adm release info -o template --template '{{ .metadata.version }}' ${image}"
            )

        (major, minor) = commonlib.extractMajorMinorVersionNumbers(tag)
        ocpVersion = "$major.$minor"

        (arch, priv) = releaselib.getReleaseTagArchPriv(tag)
        suffix = releaselib.getArchPrivSuffix(arch, priv)

        cmd = """
            tmp=\$(mktemp -d /tmp/tmp.XXXXXX)
            oc image extract --path /manifests/:\$tmp \$(oc adm release info --image-for installer ${image})
            cat \$tmp/coreos-bootimages.yaml | yq -r .data.stream | jq -r .architectures.${arch}.artifacts.qemu.release
            rm -rf \$tmp
        """
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
    rhcoslib.initialize(ocpVersion, rhcosBuild, arch, name, mirrorPrefix)

    try {
        stage("Get/Generate sync list") {
            if ( params.SYNC_LIST == "" || params.SYNC_LIST.endsWith(".json") )
                rhcoslib.rhcosSyncPrintArtifacts()
            else
                rhcoslib.rhcosSyncManualInput()
        }
        stage("Mirror artifacts") {
            rhcoslib.rhcosSyncMirrorArtifacts(mirrorPrefix, arch, rhcosBuild, name)
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
                    rhcoslib.rhcosSyncROSA()
                }
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', accessKeyVariable: 'AWS_ACCESS_KEY_ID', credentialsId: 'artjenkins_rhcos_rosa_marketplace_production', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                    rhcoslib.rhcosSyncROSA()
                }
            }
            stage("Slack notification to release channel") {
                slacklib.to(ocpVersion).say("""
                *:white_check_mark: rosa_sync (${name}) successful*
                """)
            }
        }

        // run publish_azure_marketplace when publishing RHCOS bootimages for 4.10+
        stage("Publish azure marketplace") {
            if ( buildlib.cmp_version(ocpVersion, "4.9") == 1 ) {
                build(
                    job: 'build%252Fpublish_azure_marketplace',
                    wait: true,
                    parameters: [
                        string(name: 'VERSION', value: ocpVersion),
                        booleanParam(name: 'DRY_RUN', value: params.DRY_RUN),
                    ]
                )
            } else {
                echo "Skipping publish azure marketplace due to ocpversion lower than 4.10."
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
        commonlib.safeArchiveArtifacts(rhcoslib.artifacts)
        buildlib.cleanWorkspace()
    }
}

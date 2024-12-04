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
                    commonlib.dryrunParam(),
                    commonlib.mockParam(),
                ],
            ]
        ]
    )

    commonlib.checkMock()

    if (!params.RELEASE_TAG) {
        error("Need RELEASE_TAG")
    }

    tag = params.RELEASE_TAG

    (major, minor) = commonlib.extractMajorMinorVersionNumbers(tag)
    ocpVersion = "$major.$minor"

    (arch, priv) = releaselib.getReleaseTagArchPriv(tag)
    suffix = releaselib.getArchPrivSuffix(arch, priv)

    pullspec = ""
    if (tag.contains("/")) {
        // assume instead of a tag it's a pullspec e.g. to registry.ci
        if (!tag.contains(":")) error("RELEASE_TAG pullspec must include a :tag")
        pullspec = tag
        tag = tag.split(":")[-1]
    }
    if (pullspec == "") {
        if (tag.contains("nightly")) {
            pullspec = "registry.ci.openshift.org/ocp${suffix}/release${suffix}:${tag}"
        } else {
            pullspec = "quay.io/openshift-release-dev/ocp-release:${tag}"
        }
    }

    onlyIfDifferent = false
    needsHappening = true
    noLatest = params.NO_LATEST
    // for nightlies, sync them to dev dir
    // This is a special case. see: ART-10946
    if (tag.contains("nightly")) {
        name = "dev-${ocpVersion}"
        noLatest = true
        onlyIfDifferent = true
    } else {
        name = commonlib.shell(
            returnStdout: true,
            script: "oc adm release info -o template --template '{{ .metadata.version }}' ${pullspec}"
        )
    }

    cmd = """
        tmp=\$(mktemp -d /tmp/tmp.XXXXXX)
        oc image extract --path /manifests/:\$tmp \$(oc adm release info --image-for installer ${pullspec})
        cat \$tmp/coreos-bootimages.yaml | yq -r .data.stream | jq -r .architectures.${arch}.artifacts.qemu.release
        rm -rf \$tmp
    """
    rhcosBuild =  commonlib.shell(
        returnStdout: true,
        script: cmd
    ).trim()

    pattern = /$major\.$minor\.(\d+)-$arch/
    is_stable = tag ==~ pattern
    mirrorPrefix = is_stable ? ocpVersion : "pre-release"

    print("RHCOS build: $rhcosBuild, arch: $arch, mirror prefix: $mirrorPrefix")

    echo("Initializing RHCOS-${mirrorPrefix} sync: #${currentBuild.number}")
    rhcoslib.initialize(ocpVersion, rhcosBuild, arch, name, mirrorPrefix)

    try {
        stage("Get/Generate sync list") {
            rhcoslib.rhcosSyncPrintArtifacts()
	    needsHappening = rhcoslib.rhcosSyncNeedsHappening(mirrorPrefix, rhcosBuild, name, onlyIfDifferent)
        }
        stage("Mirror artifacts") {
	    if (!needsHappening) { return }
            rhcoslib.rhcosSyncMirrorArtifacts(mirrorPrefix, arch, rhcosBuild, name, noLatest)
        }
        stage("Slack notification to release channel") {
	    if (!needsHappening) { return }
            if ( !params.DRY_RUN ) {
                slacklib.to(ocpVersion).say("""
                *:white_check_mark: rhcos_sync (${mirrorPrefix}) successful*
                https://mirror.openshift.com/pub/openshift-v4/${arch}/dependencies/rhcos/${mirrorPrefix}/${name}/

                buildvm job: ${commonlib.buildURL('console')}
                """)
            }
        }

        // only run for x86_64 since no AMIs for other arches
        // only sync AMI to ROSA Marketplace account when no custom sync list is defined
        if ( arch == "x86_64") {
            stage("Mirror ROSA AMIs") {
	        if (!needsHappening) { return }
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
	        if (!needsHappening) { return }
                if ( !params.DRY_RUN ) {
                    slacklib.to(ocpVersion).say("""
                    *:white_check_mark: rosa_sync (${name}) successful*
                    """)
                }
            }
        }

        // run publish_azure_marketplace when publishing RHCOS bootimages for 4.10+
        stage("Publish azure marketplace") {
	    if (!needsHappening) { return }
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
        if ( !params.DRY_RUN ) {
            slacklib.to(ocpVersion).say("""
            *:heavy_exclamation_mark: rhcos_sync ${mirrorPrefix} failed*
            buildvm job: ${commonlib.buildURL('console')}
            """)
        }
        throw (err)
    } finally {
        commonlib.safeArchiveArtifacts(rhcoslib.artifacts)
        buildlib.cleanWorkspace()
    }
}

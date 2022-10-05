buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
slacklib = commonlib.slacklib

/**
 * Note: doozer gen-payload --apply-multi-arch requires manifest-tool to assemble manifest-list release payload images.
 * The version of manifest-tool from existing rhel7 repos was too old, so it was built and installed
 * from source on buildvm: https://github.com/estesp/manifest-tool/commit/ab59f071d40bc0bc98805adf9028e8caddc567c6
 * using go version go1.16.13 .
 */

// doozer_working must be in WORKSPACE in order to have artifacts archived
mirrorWorking = "${env.WORKSPACE}/MIRROR_working"
logLevel = ""
artifacts = []
mirroringKeys = []  // 'x86_64', 'x86_64-priv', 's390x', etc
imageList = ""
excludeArches = []

def initialize() {
    buildlib.cleanWorkdir(mirrorWorking)
    if (params.DRY_RUN) {
        currentBuild.displayName += " [DRY_RUN]"
    }
    def arches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}").toList()
    if ( params.EXCLUDE_ARCHES ) {
        excludeArches = commonlib.parseList(params.EXCLUDE_ARCHES)
        currentBuild.displayName += " [EXCLUDE ${excludeArches.join(', ')}]"
        if ( !arches.containsAll(excludeArches) )
            error("Trying to exclude arch ${excludeArches} not present in known arches ${arches}")
        arches.removeAll(excludeArches)
    }

    currentBuild.displayName += " OCP ${params.BUILD_VERSION}"
    currentBuild.description = "Arches: ${arches.join(', ')}"
    if ( params.DEBUG ) {
        logLevel = " --loglevel=5 "
    }
    imageList = commonlib.cleanCommaList(params.IMAGES)
    if ( imageList ) {
        echo("Only syncing specified images: ${imageList}")
        currentBuild.description += "<br>Images: ${imageList}"
        currentBuild.displayName += " [${imageList.split(',').size()} Image(s)]"
    }
}


// ######################################################################
// Determine the content to update in the ART latest imagestreams
// and apply those changes on the CI cluster. The verb will also mirror
// out images to the quay monorepo.
def buildSyncGenInputs() {
    echo("Generating and applying imagestream updates")
    def output_dir = "gen-payload-artifacts" // will be relative to env.WORKSPACE
    artifacts.addAll(["${output_dir}/*", "MIRROR_working/debug.log"])
    def images = imageList ? "--images '${imageList}'" : ''
    def excludeArchesParam = ""
    def multiArchApply = ""

    if (!params.SKIP_MULTI_ARCH_PAYLOAD) {
        // group/assemblies that don't have multi_arch.enabled=true will be skipped
        // by doozer code, so this is safe to pass in to any release.
        multiArchApply = "--apply-multi-arch"
    }

    for (arch in excludeArches) {
        excludeArchesParam += " --exclude-arch ${arch}"
    }

    def dryRunParams = params.DRY_RUN ? '--skip-gc-tagging --moist-run' : ''

    def groupParam = "openshift-${params.BUILD_VERSION}"
    if (params.DOOZER_DATA_GITREF) {
        groupParam += "@${params.DOOZER_DATA_GITREF}"
    }

    withEnv(["KUBECONFIG=${buildlib.ciKubeconfig}", "https_proxy=", "http_proxy="]) {
        sh "rm -rf ${env.WORKSPACE}/${output_dir}"
        buildlib.doozer """
${images}
--working-dir "${mirrorWorking}"
--data-path "${params.DOOZER_DATA_PATH}"
--group ${groupParam}
release:gen-payload
--output-dir "${env.WORKSPACE}/${output_dir}"
--apply
${params.EMERGENCY_IGNORE_ISSUES?'--emergency-ignore-issues':''}
${multiArchApply}
${excludeArchesParam}
${dryRunParams}
"""
    }

    if (params.ASSEMBLY == "stream" && !params.DOOZER_DATA_GITREF) {
        try {
            buildlib.oc("${logLevel} --kubeconfig ${buildlib.ciKubeconfig} registry login")
            def (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.BUILD_VERSION)
            // Starting with 4.12, ART is responsible for populating the CI imagestream (-n ocp is/4.12) with
            // references to the latest machine-os-content, rhel-coreos-8, rhel-coreos-8-extensions (and
            // potentially more with rhel9). If this is failing, it must be treated as a priority since
            // CI will begin falling being nightly CoreOS content.
            if ( major > 4 || minor >= 12 ) {
                def arches = buildlib.branch_arches(groupParam)
                // Gather a list of tags to mirror to the CI imagestream. This will include rhel-coreos-* to pick up
                // any future RHCOS RHEL versions (e.g. rhel-coreos-9).
                def tags = commonlib.shell(
                    script: """
                    oc --kubeconfig ${buildlib.ciKubeconfig} get -n ocp is/${params.BUILD_VERSION}-art-latest -o=json | jq .spec.tags[].name -r | grep -e machine-os-content -e rhel-coreos-
                    """,
                    returnStdout: true
                )
                tags_to_transfer = tags.trim().split()
                for ( String archSuffix : commonlib.goArchSuffixes ) {
                    if ( archSuffix.contains("multi") ) {
                        continue
                    }
                    for (String tag : tags_to_transfer) {
                        // isolate the pullspec trom the ART imagestream tag (e.g. quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:c1c7dde05f31052823289373400f8549e118f473d08aebf81e81235bd7cd5e80)
                        def tag_pullspec = commonlib.shell(
                            script: """
                            oc --kubeconfig ${buildlib.ciKubeconfig} -n ocp${archSuffix} get istag/${params.BUILD_VERSION}-art-latest${archSuffix}:${tag} -o=json | jq .tag.from.name -r
                            """,
                            returnStdout: true
                        ).trim()
                        // tag the pull spec into the CI imagestream (is/4.x) with the same tag name.
                        commonlib.shell(
                            script: """
                            oc --kubeconfig ${buildlib.ciKubeconfig} -n ocp${archSuffix} tag ${tag_pullspec} ${params.BUILD_VERSION}:${tag}
                            """,
                            returnStdout: true
                        )
                    }
                }
            }
        } catch (goal_ex) {
            slackChannel = slacklib.to(params.BUILD_VERSION)
            slackChannel.failure( "Unable to mirror CoreOS images to CI for ${params.BUILD_VERSION}", goal_ex )
        }
    }

    if (params.PUBLISH) {
        buildlib.oc("${logLevel} --kubeconfig ${buildlib.ciKubeconfig} registry login")
        for(file in findFiles(glob: "${output_dir}/updated-tags-for.*.yaml")) {
            def meta = readYaml(file: "${file}")['metadata']
            def namespace = meta['namespace']
            def reponame = namespace.replace("ocp", "release")
            def name = "${params.BUILD_VERSION}.0-${params.ASSEMBLY}"  // must be semver
            def image = "registry.ci.openshift.org/${namespace}/${reponame}:${name}"
            def cmd = """
                adm release new --to-image=${image} --name ${name} --reference-mode=source
                -n ${meta['namespace']} --from-image-stream ${meta['name']}
            """

            if ( params.DRY_RUN ) {
                echo("Would have created the release image as follows: \noc ${cmd}")
                continue
            }
            retry(3) {  // just to get past flakes
                sleep(5)
                buildlib.oc("${logLevel} --kubeconfig ${buildlib.ciKubeconfig} ${cmd}")
            }
            currentBuild.description += "<br>Published ${image}"
        }
    }
}

def backupAllImageStreams() {
    def allNameSpaces = ["ocp", "ocp-priv", "ocp-s390x", "ocp-s390x-priv", "ocp-ppc64le", "ocp-ppc64le-priv", "ocp-arm64", "ocp-arm64-priv"]
    for (ns in allNameSpaces) {
        def yaml = buildlib.oc("--kubeconfig ${buildlib.ciKubeconfig} get is -n ${ns} -o yaml", [capture: true])
        writeFile file:"${ns}.backup.yaml", text: yaml
        // Also backup the upgrade graph for the releases
        def ug = buildlib.oc("--kubeconfig ${buildlib.ciKubeconfig} get secret/release-upgrade-graph -n ${ns} -o yaml", [capture: true])
        writeFile file:"${ns}.release-upgrade-graph.backup.yaml", text: ug
    }
    commonlib.shell("tar zcvf app.ci-backup.tgz *.backup.yaml && rm *.backup.yaml")
    commonlib.safeArchiveArtifacts(["app.ci-backup.tgz"])
}

return this

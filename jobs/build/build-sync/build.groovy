buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
slacklib = commonlib.slacklib

/**
 * Note: doozer gen-payload --apply-multi-arch requires manifest-tool to assemble manifest-list release payload images.
 * The version of manifest-tool from existing rhel7 repos was too old, so it was built and installed
 * from souce on buildvm: https://github.com/estesp/manifest-tool/commit/89982ba85299a184a8e987c8bba1e7478f6f8b31
 * using go version go1.15.14 .
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
    for(arch in excludeArches)
        excludeArchesParam += " --exclude-arch ${arch}"
    def dryRunParams = params.DRY_RUN ? '--skip-gc-tagging --moist-run' : ''
    withEnv(["KUBECONFIG=${buildlib.ciKubeconfig}"]) {
        sh "rm -rf ${env.WORKSPACE}/${output_dir}"
        buildlib.doozer """
${images}
--working-dir "${mirrorWorking}"
--data-path "${params.DOOZER_DATA_PATH}"
--group 'openshift-${params.BUILD_VERSION}'
release:gen-payload
--output-dir "${env.WORKSPACE}/${output_dir}"
--apply
${params.EMERGENCY_IGNORE_ISSUES?'--emergency-ignore-issues':''}
${excludeArchesParam}
${dryRunParams}
"""
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

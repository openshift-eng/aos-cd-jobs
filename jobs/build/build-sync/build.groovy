buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
slacklib = commonlib.slacklib

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
// and apply those changes on the CI cluster. The verb will also mirroring
// out images to the quay monorepos.
def buildSyncGenInputs() {
    echo("Generating SRC=DEST and ImageStreams for arches")
    def images = imageList ? "--images '${imageList}'" : ''
    def excludeArchesParam = ""
    for(arch in excludeArches)
        excludeArchesParam += " --exclude-arch ${arch}"
    def dryRunParams = params.DRY_RUN ? '--skip-gc-tagging --moist-run' : ''
    withEnv(["KUBECONFIG=${buildlib.ciKubeconfig}"]) {
        sh "rm -rf ${env.WORKSPACE}/gen-payload-artifacts"
        buildlib.doozer """
${images}
--working-dir "${mirrorWorking}"
--data-path "${params.DOOZER_DATA_PATH}"
--group 'openshift-${params.BUILD_VERSION}'
release:gen-payload
--output-dir "${env.WORKSPACE}/gen-payload-artifacts"
--apply
${params.EMERGENCY_IGNORE_ISSUES?'--emergency-ignore-issues':''}
${excludeArchesParam}
${dryRunParams}
"""
    }
    artifacts.addAll(["gen-payload-artifacts/*"])

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

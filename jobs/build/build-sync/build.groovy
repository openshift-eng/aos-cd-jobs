buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

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
        currentBuild.description += "\nImages: ${imageList}"
        currentBuild.displayName += " [${imageList.split(',').size()} Image(s)]"
    }
}


// ######################################################################
// This will create a list of SOURCE=DEST strings in the output
// file(s). Will take a few minutes because we must query brew and the
// registry for each image.
def buildSyncGenInputs() {
    echo("Generating SRC=DEST and ImageStreams for arches")
    def images = imageList ? "--images '${imageList}'" : ''
    def brewEventID = params.BREW_EVENT_ID? "--event-id '${params.BREW_EVENT_ID}'" : ''
    def excludeArchesParam = ""
    for(arch in excludeArches)
        excludeArchesParam += " --exclude-arch ${arch}"
    buildlib.doozer """
${images}
--working-dir "${mirrorWorking}" --group 'openshift-${params.BUILD_VERSION}'
release:gen-payload
--is-name ${params.BUILD_VERSION}-art-latest
--organization ${params.ORGANIZATION}
--repository ${params.REPOSITORY}
${brewEventID}${excludeArchesParam}
"""
    echo("Generated files:")
    echo("######################################################################")
    def mirroringFiles = findFiles(glob: 'src_dest.*').collect{ it.path }
    for (f in mirroringFiles) {
        echo("######################################################################")
        echo(f)
        echo(readFile(file: f))
    }
    mirroringKeys = mirroringFiles.collect{(it.split("\\.") as List).last()} // src_dest.x86_64 -> x86_64
    echo("Moving generated files into working directory for archival purposes")
    sh("mv src_dest* ${mirrorWorking}/")
    sh("mv image_stream*.yaml ${mirrorWorking}/")
    artifacts.addAll(["MIRROR_working/src_dest*", "MIRROR_working/image_stream*"])
    try {
        artifacts.addAll(["MIRROR_working/state.yaml"])
        state = readYaml(file: "MIRROR_working/state.yaml")
        if (state.required_fail > 0 || state.optional_fail > 0) {
            echo "Not all images are updated. See Doozer logs and state.yaml"
            currentBuild.result = "UNSTABLE"
        }
    } catch (ex) {
        echo "Unable to read MIRROR_working/state.yaml"
        currentBuild.result = "UNSTABLE"
    }
}

// ######################################################################
// Now run the actual mirroring commands. We wrap this in a retry()
// loop because it is known to fail occassionally depending on the
// health of the source/destination endpoints.
def buildSyncMirrorImages() {
    for ( String key: mirroringKeys ) {
        retry ( 3 ) {
            echo("Attempting to mirror: ${key}")
            // Always login again. It may expire between loops
            // depending on amount of time elapsed
            buildlib.registry_quay_dev_login()
            def dryRun = "--dry-run=${params.DRY_RUN ? 'true' : 'false'}"
            buildlib.oc "${logLevel} image mirror ${dryRun} --filename=${mirrorWorking}/src_dest.${key}"
        }
    }
}

def backupAllImageStreams() {
    def allNameSpaces = ["ocp", "ocp-priv", "ocp-s390x", "ocp-s390x-priv", "ocp-ppc64le", "ocp-ppc64le-priv", "ocp-arm64", "ocp-arm64-priv"]
    for (ns in allNameSpaces) {
        def yaml = buildlib.oc("--kubeconfig ${buildlib.ciKubeconfig} get is -n ${ns} -o yaml", [capture: true])
        writeFile file:"${ns}.backup.yaml", text: yaml
    }
    commonlib.shell("tar zcvf api.ci-backup.tgz *.backup.yaml && rm *.backup.yaml")
    commonlib.safeArchiveArtifacts(["api.ci-backup.tgz"])
}


def buildSyncApplyImageStreams() {
    echo("Updating ImageStream's")
    def failures = []
    for ( String key: mirroringKeys ) {
        def isFile = "${mirrorWorking}/image_stream.${key}.yaml"
        def imageStream = readYaml file: isFile
        def theStream = imageStream.metadata.name
        def namespace = imageStream.metadata.namespace

        // Get the current IS and save it to disk. We may need this for debugging.
        def currentIS = getImageStream(theStream, namespace)
        writeJSON(file: "pre-apply-${namespace}-${theStream}.json", json: currentIS)
        artifacts.addAll(["pre-apply-${namespace}-${theStream}.json"])

        // We check for updates by comparing the object's 'resourceVersion'
        def currentResourceVersion = currentIS.metadata.resourceVersion
        echo("Current resourceVersion for ${theStream}: ${currentResourceVersion}")

        // Ok, try the update. Jack that debug output up high, just in case
        echo("Going to apply this ImageStream:")
        echo(readFile(file: isFile))
        def dryRun = "--dry-run=${params.DRY_RUN ? 'client' : 'none'}"
        buildlib.oc("${logLevel} apply ${dryRun} --filename=${isFile} --kubeconfig ${buildlib.ciKubeconfig}")

        // Now we verify that the change went through and save the bits as we go
        def newIS = getImageStream(theStream, namespace)
        writeJSON(file: "post-apply-${namespace}-${theStream}.json", json: newIS)
        artifacts.addAll(["post-apply-${namespace}-${theStream}.json"])
        def newResourceVersion = newIS.metadata.resourceVersion
        if ( newResourceVersion == currentResourceVersion ) {
            if ( params.DRY_RUN ) {
                echo("IS `.metadata.resourceVersion` has not updated, which is expected in a dry run.")
                continue
            }
            echo("IS `.metadata.resourceVersion` has not updated, it should have updated. Please use the debug info above to report this issue")
            currentBuild.description += "\nImageStream update failed for ${key}"
            failures << key
        }
    }
    if (failures) {
        throw new Exception("Image Stream did not update for ${failures}")
    }
}

// Get a JSON object of the named image stream in the ocp
// namespace. The image stream is also saved locally for debugging
// purposes.
def getImageStream(is, ns) {
    def isJson = readJSON(text: buildlib.oc(" get is ${is} -n ${ns} -o json --kubeconfig ${buildlib.ciKubeconfig}", [capture: true]))
    return isJson
}

return this

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

// doozer_working must be in WORKSPACE in order to have artifacts archived
mirrorWorking = "${env.WORKSPACE}/MIRROR_working"
logLevel = ""
images = ""
dryRun = "--dry-run=false"
artifacts = []
// ######################################################################
// Single arch options

// Locally stored image stream stub
baseImageStream = "/home/jenkins/base-art-latest-imagestream-${params.BUILD_VERSION}.yaml"
// Kubeconfig allowing ART to interact with api.ci.openshift.org
ciKubeconfig = "/home/jenkins/kubeconfigs/art-publish.kubeconfig"

// See 'oc image mirror --help' for more information.
// This is the template for the SRC=DEST strings mentioned above
// in the case of mirroring just a single arch.
ocFmtStr = "registry.reg-aws.openshift.com:443/{repository}=quay.io/${params.ORGANIZATION}/${params.REPOSITORY}:{version}-{release}-{image_name_short}"
// End single arch options
// ######################################################################

// Multiarch
// Exactly how many arches does this branch support?
arches = []
multiarch = false

def initialize() {
    buildlib.cleanWorkdir(mirrorWorking)
    arches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}").toList()

    /**
     * We need to process x86_64 for some of our work. This is because building
     * non-x86 releases requires the x86_64 imagestream to have been populated
     * with a 'cli' tag, which the release controller will then use for non-x86
     * release payloads.
     */
    arches.remove('x86_64')
    arches.add(0, 'x86_64')

    multiarch = arches.size() > 1
    if ( params.NOOP) {
	dryRun = "--dry-run=true"
	currentBuild.displayName += " [NOOP]"
    }
    if ( multiarch ) {
	currentBuild.displayName += " OCP ${params.BUILD_VERSION} - ${arches.join(', ')}"
	currentBuild.description = "Arches: ${arches.join(', ')}"
    } else {
	currentBuild.displayName += " OCP: ${params.BUILD_VERSION}"
	currentBuild.description = "Arches: default (x86_64)"
	artifacts.addAll(["MIRROR_working/oc_mirror_input", "MIRROR_working/release-is.yaml"])
    }

    if ( params.DEBUG ) {
	logLevel = " --loglevel=5 "
    }

    if ( params.IMAGES != '' ) {
	echo("Only syncing specified images: ${params.IMAGES}")
	currentBuild.description += "\nImages: ${params.IMAGES}"
	currentBuild.displayName += " [${params.IMAGES.split(',').size()} Image(s)]"
	images = "--images ${params.IMAGES}"
    }
}


// ######################################################################
// This will create a list of SOURCE=DEST strings in the output
// file(s). Will take a few minutes because we must query brew and the
// registry for each image.
def buildSyncGenInputs() {
	echo("Generating SRC=DEST and ImageStreams for arches")
	buildlib.doozer """
${images}
--working-dir "${mirrorWorking}" --group 'openshift-${params.BUILD_VERSION}'
release:gen-payload
--is-name ${params.BUILD_VERSION}-art-latest
--organization ${params.ORGANIZATION}
--repository ${params.REPOSITORY}
"""
	echo("Generated files:")
	echo("######################################################################")
	for ( String a: arches ) {
	    echo("######################################################################")
	    echo("src_dest.${a}")
	    sh("cat src_dest.${a}")
	}
	echo("Moving generated files into working directory for archival purposes")
	sh("mv src_dest* ${mirrorWorking}/")
	sh("mv image_stream*.yaml ${mirrorWorking}/")
	artifacts.addAll(["MIRROR_working/src_dest*", "MIRROR_working/image_stream*"])
}

// ######################################################################
// Now run the actual mirroring commands. We wrap this in a retry()
// loop because it is known to fail occassionally depending on the
// health of the source/destination endpoints.
def buildSyncMirrorImages() {
    for ( String arch: arches ) {
        retry ( 3 ) {
            echo("Attempting to mirror arch: ${arch}")
            // Always login again. It may expire between loops
            // depending on amount of time elapsed
            buildlib.registry_quay_dev_login()
            buildlib.oc "${logLevel} image mirror ${dryRun} --filename=${mirrorWorking}/src_dest.${arch}"
        }
    }
}


def buildSyncApplyImageStreams() {
    echo("Updating ImageStream's")
    for ( String arch: arches ) {
        // Why be consistent when we could have more edge cases instead?
        def a = (arch == "x86_64")? "": "-${arch}"
        def theStream = "${params.BUILD_VERSION}-art-latest${a}"

        // Get the current IS and save it to disk. We may need this for debugging.
        def currentIS = getImageStream(theStream, arch)
        writeJSON(file: "pre-apply-${theStream}.json", json: currentIS)
        artifacts.addAll(["pre-apply-${theStream}.json"])

        // We check for updates by comparing the object's 'resourceVersion'
        def currentResourceVersion = currentIS.metadata.resourceVersion
        echo("Current resourceVersion for ${theStream}: ${currentResourceVersion}")

        // Ok, try the update. Jack that debug output up high, just in case
        echo("Going to apply this ImageStream:")
        sh("cat ${mirrorWorking}/image_stream.${arch}.yaml")
        buildlib.oc(" --loglevel=8 apply ${dryRun} --filename=${mirrorWorking}/image_stream.${arch}.yaml --kubeconfig ${ciKubeconfig}")

        // Now we verify that the change went through and save the bits as we go
        def newIS = getImageStream(theStream, arch)
        writeJSON(file: "post-apply-${theStream}.json", json: newIS)
        artifacts.addAll(["post-apply-${theStream}.json"])
        def newResourceVersion = newIS.metadata.resourceVersion
        if ( newResourceVersion == currentResourceVersion ) {
            echo("IS `.metadata.resourceVersion` has not updated, it should have updated. Please use the debug info above to report this issue")
            throw new Exception("Image Stream ${theStream} did not update")
        }
    }
}

// Get a JSON object of the named image stream in the ocp
// namespace. The image stream is also saved locally for debugging
// purposes.
def getImageStream(is, arch) {
    def a = (arch == "x86_64")? "ocp": "ocp-${arch}"
    def isJson = readJSON(text: buildlib.oc(" get is ${is} -n ${a} -o json --kubeconfig ${ciKubeconfig}", [capture: true]))
    return isJson
}

return this

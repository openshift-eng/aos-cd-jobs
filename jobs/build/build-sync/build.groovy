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

// Location of the SRC=DEST input file
ocMirrorInput = "${mirrorWorking}/oc_mirror_input"
// Location of the image stream to apply
ocIsObject = "${mirrorWorking}/release-is.yaml"
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
    if ( multiarch ) {
	echo("Generating SRC=DEST and ImageStreams for arches")
	buildlib.doozer """
${images}
--working-dir "${mirrorWorking}" --group 'openshift-${params.BUILD_VERSION}'
release:gen-multiarch-payload
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
    } else {
	echo("Generating SRC=DEST for one arch")
	buildlib.doozer """
${images}
--working-dir "${mirrorWorking}" --group 'openshift-${params.BUILD_VERSION}'
release:gen-payload
--src-dest ${ocMirrorInput}
--image-stream ${ocIsObject}
--is-base ${baseImageStream}
'${ocFmtStr}'
"""
	echo("Generated file:")
	echo("######################################################################")
	echo("${ocMirrorInput}")
	sh("cat ${ocMirrorInput}")
    }
}

// ######################################################################
// Now run the actual mirroring commands. We wrap this in a retry()
// loop because it is known to fail occassionally depending on the
// health of the source/destination endpoints.
def buildSyncMirrorImages() {
    if ( multiarch ) {
        for ( String arch: arches ) {
            retry ( 3 ) {
                echo("Attempting to mirror arch: ${arch}")
                // Always login again. It may expire between loops
                // depending on amount of time elapsed
                buildlib.registry_quay_dev_login()
                buildlib.oc "${logLevel} image mirror ${dryRun} --filename=${mirrorWorking}/src_dest.${arch} --filter-by-os=${arch}"
                currentBuild.description += ", ${arch}"
            }
        }
    } else {
        retry ( 3 ) {
            buildlib.registry_quay_dev_login()
            buildlib.oc "${logLevel} image mirror ${dryRun} --filename=${ocMirrorInput}"
            currentBuild.description += "\nMirrored: default arch (amd64)"
        }
    }
}


def buildSyncApplyImageStreams() {
    if ( multiarch ) {
	echo("Updating ImageStream's")
        // And one more time for each other stream
        for ( String arch: arches ) {
            echo("Going to apply this ImageStream:")
            sh("cat ${mirrorWorking}/image_stream.${arch}.yaml")
            buildlib.oc "${logLevel} apply ${dryRun} --filename=${mirrorWorking}/image_stream.${arch}.yaml --kubeconfig ${ciKubeconfig}"
            currentBuild.description += ", ${arch}"
        }
    } else {
        buildlib.oc "${logLevel} apply ${dryRun} --filename=${ocIsObject} --kubeconfig ${ciKubeconfig}"
        currentBuild.description += "\nUpdated default ImageStream (amd64)"
    }
}

return this

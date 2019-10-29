buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib



def initialize() {
    buildlib.cleanWorkdir(mirrorWorking)
    arches = buildlib.branch_arches("openshift-${params.BUILD_VERSION}")
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
	currentBuild.description = "Arches: default (amd64)"
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



return this

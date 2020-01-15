buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
rhcosWorking = "${env.WORKSPACE}/rhcos_working"
logLevel = ""
dryRun = ""
artifacts = []
baseUrl = "https://art-rhcos-ci.s3.amazonaws.com/releases/rhcos-%OCPVERSION%/%RHCOSBUILD%/%ARCH%"
metaUrl = ""
baseDir = "/srv/pub/openshift-v4/%ARCH%/dependencies/rhcos"
syncList = "rhcos-synclist-${currentBuild.number}.txt"

def initialize() {
    buildlib.cleanWorkdir(rhcosWorking)
    // Sub in those vars
    baseUrl = baseUrl.replace("%OCPVERSION%", params.BUILD_VERSION)
    baseUrl = baseUrl.replace("%RHCOSBUILD%", params.RHCOS_BUILD)
    baseUrl = baseUrl.replace("%ARCH%", params.ARCH)
    baseDir = baseDir.replace("%ARCH%", params.ARCH)
    // Actual meta.json
    metaUrl = baseUrl + "/meta.json"

    name = params.NAME

    currentBuild.displayName = "${params.NAME} - ${params.RHCOS_BUILD}:${params.ARCH} - ${params.RHCOS_MIRROR_PREFIX}"
    currentBuild.description = "Meta JSON: ${metaUrl}"

    if ( params.NOOP ) {
        dryRun = "--dry-run=true"
        currentBuild.displayName += " [NOOP]"
    }

    dir ( rhcosWorking ) {
        if ( params.SYNC_LIST == "" ) {
            sh("wget ${metaUrl}")
            artifacts.add("meta.json")
        }
    }
}

def rhcosSyncManualInput() {
    sh("wget ${params.SYNC_LIST} -O ${syncList}")
}

def rhcosSyncPrintArtifacts() {
    def imageUrls = []
    dir ( rhcosWorking ) {
        def meta = readJSON file: 'meta.json', text: ''
        meta.images.eachWithIndex { name, value, i ->
            imageUrls.add(baseUrl + "/${value.path}")
        }
    }
    currentBuild.displayName += " [${imageUrls.size()} Images]"
    echo(imageUrls.toString())
    writeFile file: syncList, text: "${imageUrls.join('\n')}"
}

def rhcosSyncMirrorArtifacts() {
    sh("scp -o StrictHostKeychecking=no ${syncList} use-mirror-upload.ops.rhcloud.com:/tmp/")
    def invokeOpts = "-- --prefix ${params.RHCOS_MIRROR_PREFIX} --version ${params.NAME} --synclist /tmp/${syncList} --basedir ${baseDir}"
    if ( params.FORCE ) {
    	invokeOpts += " --force"
    }
    if ( params.NOOP ) {
	    invokeOpts += " --test"
    }
    if ( params.NO_LATEST ) {
	    invokeOpts += " --nolatest"
    }
    if ( params.NO_MIRROR ) {
	    invokeOpts += " --nomirror"
    }

    buildlib.invoke_on_use_mirror("rhcossync.sh", invokeOpts)
}

def rhcosSyncGenDocs() {
    dir( rhcosWorking ) {
	    sh("sh ../gen-docs.sh < meta.json > rhcos-${params.RHCOS_BUILD}.adoc")
    }
    artifacts.add("rhcos_working/rhcos-${params.RHCOS_BUILD}.adoc")
}


return this

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
rhcosWorking = "${env.WORKSPACE}/rhcos_working"
logLevel = ""
dryRun = ""
artifacts = []
baseUrl = ""
metaUrl = ""
baseDir = ""
syncList = "rhcos-synclist-${currentBuild.number}.txt"

def initialize() {
    buildlib.cleanWorkdir(rhcosWorking)
    // Sub in some vars according to params
    def ocpVersion = params.BUILD_VERSION
    def rhcosBuild = params.RHCOS_BUILD
    def arch = params.ARCH
    def archSuffix = arch == "x86_64" ? "" : "-${arch}"
      // we do not plan to release a new 4.1 bootimage ever
      // 4.2 is grandfathered in without the archDir in the path
      // 4.3+ include archDir - ref. rhcos release browser
    def archDir = ocpVersion == "4.2" ? "" : "/${arch}"
    baseUrl = "https://art-rhcos-ci.s3.amazonaws.com/releases/rhcos-${ocpVersion}${archSuffix}${archDir}/${rhcosBuild}"
    baseDir = "/srv/pub/openshift-v4/${arch}/dependencies/rhcos"
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
    def invokeOpts = "--" +
        " --prefix ${params.RHCOS_MIRROR_PREFIX}" +
        " --arch ${params.ARCH}" +
        " --buildid ${params.RHCOS_BUILD}" +
        " --version ${params.NAME}" +
        " --synclist /tmp/${syncList}" +
        " --basedir ${baseDir}"
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
        // TODO
        // sh("sh ../gen-docs.sh < meta.json > rhcos-${params.RHCOS_BUILD}.adoc")
    }
    artifacts.add("rhcos_working/rhcos-${params.RHCOS_BUILD}.adoc")
}


return this

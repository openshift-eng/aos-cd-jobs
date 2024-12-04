releaselib = load("pipeline-scripts/release.groovy")
buildlib = releaselib.buildlib
commonlib = releaselib.commonlib
rhcosWorking = "rhcos_working"
logLevel = ""
artifacts = []
baseUrl = ""
metaUrl = ""
syncList = "rhcos-synclist-${currentBuild.number}.txt"
// RHCOS artifacts that were published in 4.2/4.3
// QEMU added because bare-metal IPI installs need it for now
// TODO: keep list updated for each new release
enforce_allowlist = false
rhcos_allowlist = [ "gcp", "initramfs", "iso", "kernel", "metal", "openstack", "qemu", "vmware", "dasd" ]

def initialize(ocpVersion, rhcosBuild, arch, name, mirrorPrefix) {
    buildlib.cleanWorkdir(rhcosWorking)

    baseUrl = buildlib.doozer("--quiet --group=openshift-${ocpVersion} config:read-group urls.rhcos_release_base.multi --default ''", [capture: true]).trim()
    baseUrl = "${baseUrl}/${rhcosBuild}/${arch}"

    s3MirrorBaseDir = "/pub/openshift-v4/${arch}/dependencies/rhcos"
    metaUrl = "${baseUrl}/meta.json"

    currentBuild.displayName = "${name} - ${rhcosBuild}:${arch} - ${mirrorPrefix}"
    currentBuild.description = "Meta JSON: ${metaUrl}"
    if ( params.DRY_RUN ) {
        currentBuild.displayName += " [DRY_RUN]"
    }

    dir ( rhcosWorking ) {
        sh("wget ${metaUrl} -O meta.json")
        artifacts.add("${rhcosWorking}/meta.json")
        commonlib.shell(script: "pip install awscli")
    }
}

def rhcosSyncPrintArtifacts() {
    def imageUrls = []
    dir ( rhcosWorking ) {
        def meta = readJSON file: 'meta.json', text: ''
        meta.images.eachWithIndex { name, value, i ->
            if (!enforce_allowlist || rhcos_allowlist.contains(name)) {
                imageUrls.add(baseUrl + "/${value.path}")
            }
        }
    }
    currentBuild.displayName += " [${imageUrls.size()} Images]"
    echo(imageUrls.toString())
    writeFile file: syncList, text: "${imageUrls.join('\n')}"
}

def getRhcosBuildFromMirror(rhcosMirrorPrefix, name) {
    def rhcosIdUrl = "https://mirror.openshift.com${s3MirrorBaseDir}/${rhcosMirrorPrefix}/${name}/rhcos-id.txt"
    def res = commonlib.shell(script: "curl --fail --silent --retry 3 --retry-delay 10 -L ${rhcosIdUrl}", returnAll: true)
    def rhcosId = "[NOT FOUND]"
    if (res.returnStatus == 0) {
        rhcosId = res.stdout.trim()
    }
    return rhcosId
}

def rhcosSyncNeedsHappening(rhcosMirrorPrefix, rhcosBuild, name, onlyIfDifferent) {
    if (params.FORCE) {
        return true
    }
    // check if rhcos-id is already on mirror
    def rhcosBuildOnMirror = getRhcosBuildFromMirror(rhcosMirrorPrefix, name)
    echo("RHCOS build requested to sync: ${rhcosBuild}")
    echo("RHCOS build on mirror: ${rhcosBuildOnMirror}")
    if (rhcosBuildOnMirror == rhcosBuild) {
        echo("RHCOS build is already on mirror, skipping sync")
        return false
    }
    return true && onlyIfDifferent
}


def rhcosSyncMirrorArtifacts(rhcosMirrorPrefix, arch, rhcosBuild, name, noLatest) {
    def invokeOpts = " --prefix ${rhcosMirrorPrefix}" +
        " --arch ${arch}" +
        " --buildid ${rhcosBuild}" +
        " --version ${name}"

    if ( params.DRY_RUN ) {
            invokeOpts += " --test"
    }
    if ( noLatest ) {
            invokeOpts += " --nolatest"
    }

    withCredentials([
    file(credentialsId: 'aws-credentials-file', variable: 'AWS_SHARED_CREDENTIALS_FILE'),
    string(credentialsId: 's3-art-srv-enterprise-cloudflare-endpoint', variable: 'CLOUDFLARE_ENDPOINT')]) {
        commonlib.shell("${env.WORKSPACE}/S3-rhcossync.sh ${invokeOpts} --basedir ${s3MirrorBaseDir} --synclist ${env.WORKSPACE}/${syncList}")
    }
}

def rhcosSyncROSA() {
    commonlib.shell("${env.WORKSPACE}/build-scripts/rosa-sync/rosa_sync.sh ${rhcosWorking}/meta.json ${params.DRY_RUN}")
}

return this

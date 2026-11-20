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

    // To construct rhcos build url, we do not fetch the url from group.yml
    // and instead hardcode and construct it from the rhcos build id
    // This is because we usually are on an older rhcos build after branch cut
    // e.g. 4.19 nightly will have installer build which references 4.18 rhcos build
    // but 4.19 rhcos url in group.yml will be pointing to 4.19 rhcos stream.
    // 418.94.202410090804-0 -> 4.18-9.4
    buildParts = rhcosBuild.split("\\.")
    ocpStream = ocpVersion
    minor = ocpVersion.split("\\.")
    majorNum = minor[0].toInteger()
    minorNum = minor[1].toInteger()
    if ( majorNum > 4 || (majorNum == 4 && minorNum > 18) ) {
        // For 4.19+ / 5.x+ the rhcosBuild name is in format 9.6.20250121-0
        rhelStream = buildParts[0] + '.' + buildParts[1]
        stream = "rhel-${rhelStream}"
    } else {
        // For 4.18 and below the rhcosBuild name is in format 418.94.202410090804-0
        rhelStream = buildParts[1][0] + '.' + buildParts[1][1..-1]
        stream = "${ocpStream}-${rhelStream}"
    }

    baseUrl = "https://releases-rhcos--prod-pipeline.apps.int.prod-stable-spoke1-dc-iad2.itup.redhat.com/storage/prod/streams/${stream}/builds"
    buildUrl = "${baseUrl}/${rhcosBuild}/${arch}"

    s3MirrorBaseDir = "/pub/openshift-v4/${arch}/dependencies/rhcos"
    metaUrl = "${buildUrl}/meta.json"

    currentBuild.displayName = "${name} - ${rhcosBuild}:${arch} - ${mirrorPrefix}"
    currentBuild.description = "Meta JSON: ${metaUrl}"
    if ( params.DRY_RUN ) {
        currentBuild.displayName += " [DRY_RUN]"
    }

    dir ( rhcosWorking ) {
        sh("wget ${metaUrl} -O meta.json")
        artifacts.add("${rhcosWorking}/meta.json")
    }
}

def rhcosSyncPrintArtifacts() {
    def imageUrls = []
    dir ( rhcosWorking ) {
        def meta = readJSON file: 'meta.json', text: ''
        meta.images.eachWithIndex { name, value, i ->
            if (!enforce_allowlist || rhcos_allowlist.contains(name)) {
                imageUrls.add(buildUrl + "/${value.path}")
            }
        }
    }
    currentBuild.displayName += " [${imageUrls.size()} Images]"
    echo(imageUrls.toString())
    writeFile file: syncList, text: "${imageUrls.join('\n')}"
}

def getRhcosBuildFromMirror(rhcosMirrorPrefix, name) {
    def rhcosIdUrl = "https://mirror.openshift.com${s3MirrorBaseDir}/${rhcosMirrorPrefix}/${name}/rhcos-id.txt"
    def res = commonlib.shell(script: "curl --fail --silent --retry 3 --retry-all-errors --retry-delay 10 -L ${rhcosIdUrl}", returnAll: true)
    def rhcosId = "[NOT FOUND]"
    if (res.returnStatus == 0) {
        rhcosId = res.stdout.trim()
    }
    return rhcosId
}

def rhcosSyncNeedsHappening(rhcosMirrorPrefix, rhcosBuild, name) {
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
    echo("Requested RHCOS build is not on mirror, sync is needed")
    return true
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

// Always attempt production after a staging failure. Live callers report staging failures
// after processing all AMIs. Production errors in a live run and interruptions propagate.
def rhcosSyncROSAWithCredentials(metaJson, dryRun) {
    def failures = []
    ['staging', 'production'].each { destination ->
        try {
            withCredentials([usernamePassword(
                credentialsId: "artjenkins_rhcos_rosa_marketplace_${destination}",
                usernameVariable: 'AWS_ACCESS_KEY_ID',
                passwordVariable: 'AWS_SECRET_ACCESS_KEY'
            )]) {
                commonlib.shell("${env.WORKSPACE}/build-scripts/rosa-sync/rosa_sync.sh ${metaJson} ${dryRun}")
            }
            if (dryRun) echo "[DRY RUN] ROSA ${destination}: identity, EC2 reads, and CopyImage permission verified"
        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException err) {
            throw err
        } catch (Exception err) {
            if (!dryRun && destination == 'production') throw err
            failures.add(destination)
            def operation = dryRun ? "[DRY RUN] ROSA ${destination} validation" : "ROSA ${destination} sync"
            echo "${operation} failed: ${err.message}"
        }
    }
    if (dryRun && failures) error("ROSA dry-run failed for: ${failures.join(', ')}; both destinations were attempted")
    return failures
}

return this

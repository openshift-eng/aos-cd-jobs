releaselib = load("pipeline-scripts/release.groovy")
buildlib = releaselib.buildlib
commonlib = releaselib.commonlib
rhcosWorking = "rhcos_working"
logLevel = ""
dryRun = ""
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

    // Example URL paths (visit https://releases-rhcos-art.apps.ocp-virt.prod.psi.redhat.com/ to view yourself):
    // 4.1 with x86 arch:       releases/rhcos-4.1/410.81.20200213.0/meta.json  (we do not plan to release a new 4.1 bootimage ever)
    // 4.1 with non-x86 arch:   N/A

    // 4.2 introduced an arch arch suffix
    // 4.2 with x86 arch:       releases/rhcos-4.2/42.81.20200213.0/meta.json
    // 4.2 with non-x86 arch:   releases/rhcos-4.2-s390x/42s390x.81.20200131.0/meta.json

    // 4.3 introduced an arch subdirectory
    // 4.3 with x86 arch:       releases/rhcos-4.3/43.81.202002130953.0/x86_64/meta.json
    // 4.3 with non-x86 arch:   releases/rhcos-4.3-s390x/43.81.202001300441.0/s390x/meta.json

    // Sub in some vars according to params
    def archSuffix = commonlib.brewSuffixForArch(arch)
    def archDir = ocpVersion == "4.2" ? "" : "/${arch}"
    baseUrl = "https://art-rhcos-ci.s3.amazonaws.com/releases/rhcos-${ocpVersion}${archSuffix}/${rhcosBuild}${archDir}"
    // Since 4.9+, rhcos meta is placed at a different location.
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(ocpVersion)
    if (major > 4 || (major == 4 && minor >=9)) {
        baseUrl = "https://releases-rhcos-art.apps.ocp-virt.prod.psi.redhat.com/storage/prod/streams/$ocpVersion/builds/$rhcosBuild/$arch"
        if (minor >= 13) {
            baseUrl = "https://releases-rhcos-art.apps.ocp-virt.prod.psi.redhat.com/storage/prod/streams/$ocpVersion-9.2/builds/$rhcosBuild/$arch"
        }
    }
    s3MirrorBaseDir = "/pub/openshift-v4/${arch}/dependencies/rhcos"
    // Actual meta.json
    metaUrl = baseUrl + "/meta.json"

    currentBuild.displayName = "${name} - ${rhcosBuild}:${arch} - ${mirrorPrefix}"
    currentBuild.description = "Meta JSON: ${metaUrl}"

    if ( params.DRY_RUN ) {
        dryRun = "--dry-run=true"
        currentBuild.displayName += " [DRY_RUN]"
    }

    dir ( rhcosWorking ) {
        if ( params.SYNC_LIST == "" || params.SYNC_LIST.endsWith(".json") ) {
            sh("wget ${params.SYNC_LIST ?: metaUrl} -O meta.json")
            artifacts.add("${rhcosWorking}/meta.json")
        }

        commonlib.shell(script: "pip install awscli")
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
            if (!enforce_allowlist || rhcos_allowlist.contains(name)) {
                imageUrls.add(baseUrl + "/${value.path}")
            }
        }
    }
    currentBuild.displayName += " [${imageUrls.size()} Images]"
    echo(imageUrls.toString())
    writeFile file: syncList, text: "${imageUrls.join('\n')}"
}

def rhcosSyncMirrorArtifacts(rhcosMirrorPrefix, arch, rhcosBuild, name) {
    def invokeOpts = " --prefix ${rhcosMirrorPrefix}" +
        " --arch ${arch}" +
        " --buildid ${rhcosBuild}" +
        " --version ${name}"

    if ( params.FORCE ) {
            invokeOpts += " --force"
    }
    if ( params.DRY_RUN ) {
            invokeOpts += " --test"
    }
    if ( params.NO_LATEST ) {
            invokeOpts += " --nolatest"
    }
    if ( params.NO_MIRROR ) {
            invokeOpts += " --nomirror"
    }

    withCredentials([aws(credentialsId: 's3-art-srv-enterprise', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
        commonlib.shell("${env.WORKSPACE}/S3-rhcossync.sh ${invokeOpts} --basedir ${s3MirrorBaseDir} --synclist ${env.WORKSPACE}/${syncList}")
    }
}

def rhcosSyncROSA() {
    commonlib.shell("${env.WORKSPACE}/build-scripts/rosa-sync/rosa_sync.sh ${rhcosWorking}/meta.json ${params.DRY_RUN}")
}

def rhcosSyncGenDocs(rhcosBuild) {
    dir( rhcosWorking ) {
        // TODO
        // sh("sh ../gen-docs.sh < meta.json > rhcos-${rhcosBuild}.adoc")
    }
    artifacts.add("${rhcosWorking}/rhcos-${rhcosBuild}.adoc")
}


return this

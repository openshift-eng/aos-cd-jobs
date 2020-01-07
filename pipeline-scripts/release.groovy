import groovy.json.*
import java.net.URLEncoder
import groovy.transform.Field

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

oc_cmd = "oc --config=/home/jenkins/kubeconfigs/art-publish.kubeconfig"

// dump important tool versions to console
def stageVersions() {
    sh "oc version"
    sh "doozer --version"
    sh "elliott --version"
}

/**
 * Determine the quay destination tag where a release image lives, based on the
 * the release name and arch (since we can now have multiple arches for each
 * release name) - make sure it includes the arch in the tag to distinguish
 * from any other releases of same name.
 *
 * e.g.:
 *   (4.2.0-0.nightly-s390x-2019-12-10-202536, s390x) remains 4.2.0-0.nightly-s390x-2019-12-10-202536
 *   (4.3.0-0.nightly-2019-12-07-121211, x86_64) becomes 4.3.0-0.nightly-2019-12-07-121211-x86_64
 */
def destReleaseTag(String releaseName, String arch) {
    return releaseName.contains(arch) ? releaseName : "${releaseName}-${arch}"
}

/**
 * Validate that we have not released the same thing already, and that
 * we have a valid advisory if needed.
 * quay_url: quay repo location for nightly images
 * name: tag for the specific image that will be released
 * advisory: if applicable, the advisory number intended for this release
 *      if less than 0 (pre-release), an advisory is not looked for.
 *      if greater than 0, this advisory is validated.
 *      if 0, the default image advisory from group.yml is validated.
 *      Valid advisories must be in QE state and have a live ID so we can
 *      include in release metadata the URL where it will be published.
 */
Map stageValidation(String quay_url, String dest_release_tag, int advisory = 0) {
    def retval = [:]
    def version = commonlib.extractMajorMinorVersion(dest_release_tag)
    echo "Verifying payload does not already exist"
    res = commonlib.shell(
            returnAll: true,
            script: "GOTRACEBACK=all ${oc_cmd} adm release info ${quay_url}:${dest_release_tag}"
    )

    if(res.returnStatus == 0){
        error("Payload ${dest_release_tag} already exists! Cannot continue.")
    }

    if (advisory < 0) {
        // pre-release; do not look for any advisory to exist.
        return retval
    } else if (advisory) {
        // specified advisory, go find it
        echo "Verifying advisory ${advisory} exists"
        res = commonlib.shell(
                returnAll: true,
                script: "elliott --group=openshift-${version} get --json - -- ${advisory}",
            )

        if(res.returnStatus != 0){
            error("Advisory ${advisory} does not exist! Cannot continue.")
        }
    } else {
        // unspecified advisory, look for it in group.yml
        echo "Getting current advisory for OCP $version from build data..."
        res = commonlib.shell(
                returnAll: true,
                script: "elliott --group=openshift-${version} get --json - --use-default-advisory image",
            )
        if(res.returnStatus != 0) {
            error("🚫 Advisory number for OCP $version couldn't be found from ocp_build_data.")
        }
    }

    def advisoryInfo = readJSON text: res.stdout
    retval.advisoryInfo = advisoryInfo
    echo "Verifying advisory ${advisoryInfo.id} (https://errata.engineering.redhat.com/advisory/${advisoryInfo.id}) status"
    if (advisoryInfo.status != 'QE') {
        error("🚫 Advisory ${advisoryInfo.id} is not in QE state.")
    }
    echo "✅ Advisory ${advisoryInfo.id} is in QE state."

    // Extract live ID from advisory info
    // Examples:
    // - advisory with live ID:
    //     "errata_id": 2681,
    //     "fulladvisory": "RHBA-2019:2681-02",
    //     "id": 46049,
    //     "old_advisory": "RHBA-2019:46049-02",
    // - advisory without:
    //     "errata_id": 46143,
    //     "fulladvisory": "RHBA-2019:46143-01",
    //     "id": 46143,
    //     "old_advisory": null,
    if (advisoryInfo.errata_id != advisoryInfo.id && advisoryInfo.fulladvisory && advisoryInfo.old_advisory) {
        retval.liveID = (advisoryInfo.fulladvisory =~ /^(RH[EBS]A-\d+:\d+)-\d+$/)[0][1] // remove "-XX" suffix
        retval.errataUrl ="https://access.redhat.com/errata/${retval.liveID}"
        echo "ℹ️ Got Errata URL from advisory ${advisoryInfo.id}: ${retval.errataUrl}"
    } else {
        // Fail if live ID hasn't been assigned
        error("🚫 Advisory ${advisoryInfo.id} doesn't seem to be associated with a live ID.")
    }

    return retval
}

def getArchSuffix(arch) {
    return arch == "x86_64" ? "" : "-${arch}"
}

def stageGenPayload(dest_repo, release_name, dest_release_tag, from_release_tag, description, previous, errata_url) {
    // build metadata blob

    def metadata = ''
    if (description || errata_url) {
        metadata = "{\"description\": \"${description}\""
        if (errata_url) {
            metadata += ", \"url\": \"${errata_url}\""
        }
        metadata += "}"
    }

    def arch = getReleaseTagArch(from_release_tag)

    echo "Generating release payload"
    echo "CI release name: ${from_release_tag}"
    echo "Calculated arch: ${arch}"

    def archSuffix = getArchSuffix(arch)

    // build oc command
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release new "
    cmd += "-n ocp${archSuffix} --from-release=registry.svc.ci.openshift.org/ocp${archSuffix}/release${archSuffix}:${from_release_tag} "
    if (previous != "") {
        cmd += "--previous \"${previous}\" "
    }
    cmd += "--name ${release_name} "

    // Adding metadata will change the payload sha. Ideally, nightlies and
    // pre-release shas match, so don't add it unnecessarily.
    if (metadata) {
        cmd += "--metadata '${metadata}' "
    }
    cmd += "--to-image=${dest_repo}:${dest_release_tag} "

    if (params.DRY_RUN){
        cmd += "--dry-run=true "
    }

    def stdout = commonlib.shell(
        script: cmd,
        returnStdout: true
    )

    payloadDigest = parseOcpRelease(stdout)

    currentBuild.description += " ${payloadDigest}"
}

@NonCPS
def parseOcpRelease(text) {
    text.eachLine {
        if (it =~ /^sha256:/) {
            return it.split(' ')[0]
        }
    }
}

def stageSetClientLatest(from_release_tag, arch, client_type) {
    if (params.DRY_RUN) {
        echo "Would have tried to set latest for ${from_release_tag} (client type: ${client_type}, arch: {$arch})"
        return
    }

    build(
        job: 'build%2Fset_client_latest',
        parameters: [
            buildlib.param('String', 'RELEASE', from_release_tag),
            buildlib.param('String', 'CLIENT_TYPE', client_type),
            buildlib.param('String', 'ARCHES', arch),
        ]
    )

}

def stageTagRelease(quay_url, release_name, release_tag, arch) {
    def archSuffix = getArchSuffix(arch)
    def cmd = "GOTRACEBACK=all ${oc_cmd} tag ${quay_url}:${release_tag} ocp${archSuffix}/release${archSuffix}:${release_name}"

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return
    }

    commonlib.shell(
        script: cmd
    )
}


// this function is only use for build/release job
// also returns the latest release info from the given release stream
// @param releaseStream release stream name. e.g. "4-stable" or "4-stable-s390x"
// @param releaseName release name. e.g. "4.2.1"
// @return latest release info
def Map stageWaitForStable(String releaseStream, String releaseName) {
    def count = 0
    def stable = ""
    Map release

    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(releaseName)
    def queryParams = [
        "in": ">${major}.${minor}.0-0 < ${major}.${minor + 1}.0-0"
    ]
    def queryString = queryParams.collect {
            (URLEncoder.encode(it.key, "utf-8") + "=" +  URLEncoder.encode(it.value, "utf-8"))
        }.join('&')

    // There are different release controllers for OCP - one for each architecture.
    RELEASE_CONTROLLER_URL = commonlib.getReleaseControllerURL(releaseStream)

    def apiEndpoint = "${RELEASE_CONTROLLER_URL}/api/v1/releasestream/${URLEncoder.encode(releaseStream, "utf-8")}/latest"
    def url = "${apiEndpoint}?${queryString}"

    if (params.DRY_RUN) {
        echo "Would poll URL: \n ${url}"
        return null
    }

    // 2019-05-23 - As of now jobs will not be tagged as `Accepted`
    // until they pass an upgrade test, hence the 3 hour wait loop
    while (count < 36) { // wait for 5m * 36 = 180m = 3 hours
        def response = null
        try {
            response = httpRequest(
                url: url,
                httpMode: 'GET',
                acceptType: 'APPLICATION_JSON',
                timeout: 30,
            )
            release = readJSON text: response.content
            stable = release.name
            echo "stable=${stable}"
            // found, move on
            if (stable == releaseName)
                return release
        } catch (ex) {
            echo "Error fetching latest stable: ${ex}"
        }

        count++
        sleep(300) //wait for 5 minutes between tries
    }

    if (stable != releaseName){
        error("Stable release has not updated to ${releaseName} in the allotted time. Aborting.")
    }
}

def stageGetReleaseInfo(quay_url, release_tag){
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release info --pullspecs ${quay_url}:${release_tag}"

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return "Dry Run - No Info"
    }

    def res = commonlib.shell(
        returnAll: true,
        script: cmd
    )

    if (res.returnStatus != 0){
        error(res.stderr)
    }

    return res.stdout.trim()
}

def stageAdvisoryUpdate() {
    // Waiting on new elliott features from Sam for this.
    echo "Empty Stage"
}

def stageCrossRef() {
    // cross ref tool not ready yet
    echo "Empty Stage"
}

def stagePublishClient(quay_url, from_release_tag, release_name, arch, client_type) {
    def MIRROR_HOST = "use-mirror-upload.ops.rhcloud.com"
    def MIRROR_V4_BASE_DIR = "/srv/pub/openshift-v4"

    // Anything under this directory will be sync'd to MIRROR_HOST /srv/pub/openshift-v4/...
    def BASE_TO_MIRROR_DIR="${WORKSPACE}/to_mirror/openshift-v4"
    sh "rm -rf ${BASE_TO_MIRROR_DIR}"

    // From the newly built release, extract the client tools into the workspace following the directory structure
    // we expect to publish to on the use-mirror system.
    def CLIENT_MIRROR_DIR="${BASE_TO_MIRROR_DIR}/${arch}/clients/${client_type}/${release_name}"
    sh "mkdir -p ${CLIENT_MIRROR_DIR}"
    def tools_extract_cmd = "MOBY_DISABLE_PIGZ=true GOTRACEBACK=all oc adm release extract --tools --command-os='*' -n ocp " +
                                " --to=${CLIENT_MIRROR_DIR} --from ${quay_url}:${from_release_tag}"

    if (!params.DRY_RUN) {
        commonlib.shell(script: tools_extract_cmd)
    } else {
        echo "Would have run: ${tools_extract_cmd}"
    }

    // DO NOT use --delete. We only built a part of openshift-v4 locally and don't want to remove
    // anything on the mirror.
    rsync_cmd = "rsync -avzh --chmod=a+rwx,g-w,o-w -e 'ssh -o StrictHostKeyChecking=no' "+
                " ${BASE_TO_MIRROR_DIR}/ ${MIRROR_HOST}:${MIRROR_V4_BASE_DIR}/ "

    if ( ! params.DRY_RUN ) {
        commonlib.shell(script: rsync_cmd)
        commonlib.shell(script: "ssh -o StrictHostKeyChecking='no' ${MIRROR_HOST} timeout 15m /usr/local/bin/push.pub.sh openshift-v4")
    } else {
        echo "Not mirroring; would have run: ${rsync_cmd}"
    }

}

/**
 * Derive an architecture name from a CI release tag.
 * e.g. 4.1-art-latest-s390x-2019-11-08-213727  will return s390x
 */
def getReleaseTagArch(from_release_tag) {
    // 4.1.0-0.nightly-s390x-2019-11-08-213727  ->   [4.1.0, 0.nightly, s390x, 2019, 11, 08, 213727]
    def nameComponents = from_release_tag.split('-')
    def arch = nameComponents[2]
    try {
        arch.toInteger() // this is either year or an arch; arches will throw an exception in attempt
        arch = 'x86_64'  // If there was no arch, this is x86
    } catch ( e ) {
        // The arch is not a year, so it is what we are looking for
    }
    echo "Derived architecture based on release tag name: ${arch}"
    return arch
}

def void sendReleaseCompleteMessage(Map release, int advisoryNumber, String advisoryLiveUrl, String releaseStreamName='4-stable', String providerName = 'Red Hat UMB', String arch = 'x86_64') {

    if (params.DRY_RUN) {
        echo "Would have sent release complete message"
        return
    }

    def releaseName = release.name
    def message = [
        "contact": [
            "url": "https://mojo.redhat.com/docs/DOC-1178565",
            "team": "OpenShift Automatic Release Team (ART)",
            "email": "aos-team-art@redhat.com",
            "name": "ART Jobs",
            "slack": "#aos-art",
        ],
        "run": [
            "url": env.BUILD_URL,
            "log": "${env.BUILD_URL}console",
        ],
        "artifact": [
            "type": "ocp-release",
            "name": "ocp-release",
            "version": releaseName,
            "nvr": "ocp-release-${releaseName}",
            "architecture": arch,
            "release_stream": releaseStreamName,
            "release": release,
            "advisory": [
                "number": advisoryNumber,
                "live_url": advisoryLiveUrl,
            ],
        ],
        "generated_at": new Date().format("yyyy-MM-dd'T'HH:mm:ss'Z'", TimeZone.getTimeZone('UTC')),
        "version": "0.2.3",
    ]

    timeout(3) {
        def sendResult = sendCIMessage(
            messageProperties:
                """release=${releaseName}
                release_stream: ${releaseStreamName}
                product=OpenShift Container Platform
                """,
            messageType: 'Custom',
            failOnError: true,
            overrides: [topic: "VirtualTopic.eng.ci.art.ocp-release.complete"],
            providerName: providerName,
            messageContent: JsonOutput.toJson(message),
        )
        echo 'Message sent.'
        echo "Message ID: ${sendResult.getMessageId()}"
        echo "Message content: ${sendResult.getMessageContent()}"
    }
}

def signArtifacts(Map signingParams) {
    build(
        job: "/signing-jobs/signing%2Fsign-artifacts",
        propagate: false,
        parameters: [
            string(name: "NAME", value: signingParams.name),
            string(name: "SIGNATURE_NAME", value: signingParams.signature_name),
            string(name: "CLIENT_TYPE", value: signingParams.client_type),
            booleanParam(name: "DRY_RUN", value: signingParams.dry_run),
            string(name: "ENV", value: signingParams.env),
            string(name: "KEY_NAME", value: signingParams.key_name),
            string(name: "ARCH", value: signingParams.arch),
            string(name: "DIGEST", value: signingParams.digest),
        ]
    )
}

return this

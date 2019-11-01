import groovy.json.*
import java.net.URLEncoder
import groovy.transform.Field

@Field final RELEASE_CONTROLLER_URL = "https://openshift-release.svc.ci.openshift.org"

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
Map stageValidation(String quay_url, String name, int advisory = 0) {
    def retval = [:]
    def version = commonlib.extractMajorMinorVersion(name)
    echo "Verifying payload does not already exist"
    res = commonlib.shell(
            returnAll: true,
            script: "GOTRACEBACK=all ${oc_cmd} adm release info ${quay_url}:${name}"
    )

    if(res.returnStatus == 0){
        error("Payload ${name} already exists! Cannot continue.")
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

def stageGenPayload(quay_url, name, from_release_tag, description, previous, errata_url) {
    // build metadata blob
    def metadata = "{\"description\": \"${description}\""
    if (errata_url) {
        metadata += ", \"url\": \"${errata_url}\""
    }
    metadata += "}"

    // build oc command
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release new "
    cmd += "--from-release=registry.svc.ci.openshift.org/ocp/release:${from_release_tag} "
    if (previous != "") {
        cmd += "--previous \"${previous}\" "
    }
    cmd += "--name ${name} "
    cmd += "--metadata '${metadata}' "
    cmd += "--to-image=${quay_url}:${name} "

    if (params.DRY_RUN){
        cmd += "--dry-run=true "
    }

    commonlib.shell(
            script: cmd
    )
}

def stageTagRelease(quay_url, name) {
    def cmd = "GOTRACEBACK=all ${oc_cmd} tag ${quay_url}:${name} ocp/release:${name}"

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
// @param releaseStream release stream name. e.g. "4-stable"
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

def stageGetReleaseInfo(quay_url, name){
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release info --pullspecs ${quay_url}:${name}"

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

def stageClientSync(stream, path) {
    if (params.DRY_RUN) {
        echo "Would have run oc_sync job"
        return
    }

    build(
        job: 'build%2Foc_sync',
        parameters: [
            buildlib.param('String', 'STREAM', stream),
            buildlib.param('String', 'OC_MIRROR_DIR', path),
        ]
    )
}

def stageSetClientLatest(name, path) {
    if (params.DRY_RUN) {
        echo "Would have run set_client_latest job"
        return
    }

    build(
            job: 'build%2Fset_client_latest',
            parameters: [
                    buildlib.param('String', 'RELEASE', name),
                    buildlib.param('String', 'OC_MIRROR_DIR', path),
            ]
    )
}

def stageAdvisoryUpdate() {
    // Waiting on new elliott features from Sam for this.
    echo "Empty Stage"
}

def stageCrossRef() {
    // cross ref tool not ready yet
    echo "Empty Stage"
}

def void sendReleaseCompleteMessage(Map release, int advisoryNumber, String advisoryLiveUrl, String releaseStreamName='4-stable', String providerName = 'Red Hat UMB') {
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

return this

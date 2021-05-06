import groovy.json.*
import java.net.URLEncoder
import groovy.transform.Field
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.TemporalAdjusters

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
slacklib = commonlib.slacklib

oc_cmd = "oc --kubeconfig=${buildlib.ciKubeconfig}"

// dump important tool versions to console
def stageVersions() {
    sh "oc version"
    buildlib.doozer "--version"
    buildlib.elliott "--version"
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
Map stageValidation(String quay_url, String dest_release_tag, int advisory = 0, boolean permitPayloadOverwrite = false, boolean permitAnyAdvisoryState = false, String nightly, String arch, boolean skipVerifyBugs = false, boolean skipPayloadCreation = false) {
    def retval = [:]
    def version = commonlib.extractMajorMinorVersion(dest_release_tag)
    echo "Verifying payload does not already exist"
    res = commonlib.shell(
            returnAll: true,
            script: "GOTRACEBACK=all ${oc_cmd} adm release info ${quay_url}:${dest_release_tag}"
    )

    if(res.returnStatus == 0){
        if (skipPayloadCreation) {
            echo "A payload with this name already exists. Will skip payload creation."
        } else if ( permitPayloadOverwrite ) {
            def cd = currentBuild.description
            currentBuild.description = "${currentBuild.description} - INPUT REQUIRED"
            input 'A payload with this name already exists. Overwriting it is destructive if this payload has been publicly released. Proceed anyway?'
            currentBuild.description = cd
        } else {
            error("Payload ${dest_release_tag} already exists! Cannot continue.")
        }
    } else {
        if (skipPayloadCreation) {
            error("Payload ${dest_release_tag} doesn't exist! Cannot continue.")
        }
    }

    if (advisory < 0) {
        // pre-release; do not look for any advisory to exist.
        return retval
    } else if (advisory) {
        // specified advisory, go find it
        echo "Verifying advisory ${advisory} exists"
        res = commonlib.shell(
                returnAll: true,
                script: "${buildlib.ELLIOTT_BIN} --group=openshift-${version} get --json - -- ${advisory}",
            )

        if(res.returnStatus != 0){
            error("Advisory ${advisory} does not exist! Cannot continue.")
        }
    } else {
        // unspecified advisory, look for it in group.yml
        echo "Getting current advisory for OCP $version from build data..."
        res = commonlib.shell(
                returnAll: true,
                script: "${buildlib.ELLIOTT_BIN} --group=openshift-${version} get --json - --use-default-advisory image",
            )
        if(res.returnStatus != 0) {
            error("🚫 Advisory number for OCP $version couldn't be found from ocp_build_data.")
        }
    }

    def advisoryInfo = readJSON text: res.stdout
    retval.advisoryInfo = advisoryInfo
    echo "Verifying advisory ${advisoryInfo.id} (https://errata.engineering.redhat.com/advisory/${advisoryInfo.id}) status"
    if (advisoryInfo.status != 'QE' && permitAnyAdvisoryState == false) {
        error("🚫 Advisory ${advisoryInfo.id} is not in QE state.")
    }
    echo "✅ Advisory ${advisoryInfo.id} is in ${advisoryInfo.status} state."

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

    slackChannel = slacklib.to(version)
    if (arch == 'amd64' || arch == 'x86_64') {
        echo "Verifying payload"
        res = commonlib.shell(
                returnAll: true,
                script: "elliott --group=openshift-${version} verify-payload registry.ci.openshift.org/ocp/release:${nightly} ${advisoryInfo.id}"
                )
        if (res.returnStatus != 0) {
            slackChannel.failure("elliott verify-payload failed. Advisory content does not match payload.")
            commonlib.inputRequired(slackChannel) {
                input 'Advisory content does not match payload. Proceed anyway?'
            }
        }
    }

    if (!skipVerifyBugs) {
        echo "Verify advisory bugs..."
        // NOTE: this only verifies bugs on the image advisory specified.  once
        // promotion transitions to be based on releases.yml, allow
        // verify-attached-bugs to look up all advisories there
        res = commonlib.shell(
            returnAll: true,
            script: "${buildlib.ELLIOTT_BIN} --group=openshift-${version} verify-attached-bugs ${advisoryInfo.id}",
        )
        if(res.returnStatus != 0) {
            slackChannel.failure("elliott verify-attached-bugs failed.")
            commonlib.inputRequired(slackChannel) {
                input "Bug verification failed with the following output; proceed anyway?\n${res.stdout}"
            }
        }
    }

    return retval
}

def getArchPrivSuffix(arch, priv) {
    def suffix = arch == "x86_64" ? "" : arch == "aarch64" ? "-arm64" : "-${arch}"
    if (priv)
        suffix <<= '-priv'
    return suffix
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

    def (arch, priv) = getReleaseTagArchPriv(from_release_tag)

    echo "Generating release payload"
    echo "CI release name: ${from_release_tag}"
    echo "Calculated arch: ${arch}"
    echo "Private: ${priv}"

    def suffix = getArchPrivSuffix(arch, priv)
    def publicSuffix = getArchPrivSuffix(arch, false)

    // build oc command
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release new "
    cmd += "-n ocp${publicSuffix} --from-release=registry.ci.openshift.org/ocp${suffix}/release${suffix}:${from_release_tag} "
    if (previous != "") {
        cmd += "--previous \"${previous}\" "
    }

    // Specifying --name, even if it is identical to the incoming release tag, will cause
    // the payload sha to change. Ideally, nightlies and pre-release image digests match, so
    // don't set unnecessarily.
    if (release_name != from_release_tag) {
        cmd += "--name ${release_name} "
    }

    // Adding metadata will also change the payload digest. Don't add unnecessarily.
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

def getPayloadDigest(quay_url, release_tag) {
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release info ${quay_url}:${release_tag} -o json"
    def stdout = commonlib.shell(
        script: cmd,
        returnStdout: true
    )
    def payloadInfo = readJSON(text: stdout)
    return payloadInfo['digest']
}

def getAdvisoryIds() {
    def advisories_cmd = """
        ${buildlib.DOOZER_BIN} --group ${group} config:read-group advisories --yaml 2>/dev/null |
            yq '[ to_entries[].value ]'
    """
    def stdout = commonlib.shell(
        script: advisories_cmd,
        returnStdout: true
    )
    return new JsonSlurper().parseText(stdout)
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
            buildlib.param('String', 'CHANNEL_OR_RELEASE', from_release_tag),
            buildlib.param('String', 'CLIENT_TYPE', client_type),
            buildlib.param('String', 'LINK_NAME', 'latest'),
            buildlib.param('String', 'ARCHES', arch),
        ]
    )

}

def stageTagRelease(quay_url, release_name, release_tag, arch) {
    def publicSuffix = getArchPrivSuffix(arch, false)
    def cmd = "GOTRACEBACK=all ${oc_cmd} tag ${quay_url}:${release_tag} ocp${publicSuffix}/release${publicSuffix}:${release_name}"

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

def stageCheckBlockerBug(group){
    blocker_bugs = commonlib.shell(
        returnStdout: true,
        script: "${buildlib.ELLIOTT_BIN} -g ${group} find-bugs --mode blocker --report"
    ).trim()

    echo blocker_bugs
    
    found = true
    try {
        pattern = ~"Found ([0-9]+) bugs"
        match = blocker_bugs =~ pattern
        match.find()
        found = (match[0][1] != '0')
    } catch(ex) {
        error("Could not parse Blocker bug output. Please check for blocker bug output")
    }
    if (found) {
        error('Blocker Bugs found! Aborting.')
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

def stagePublishClient(quay_url, from_release_tag, release_name, arch, client_type) {
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(release_name)
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

    commonlib.shell(script: tools_extract_cmd)
    commonlib.shell("cd ${CLIENT_MIRROR_DIR}\n" + '''
# External consumers want a link they can rely on.. e.g. .../latest/openshift-client-linux.tgz .
# So whatever we extract, remove the version specific info and make a symlink with that name.
for f in *.tar.gz *.bz *.zip *.tgz ; do

    # Is this already a link?
    if [[ -L "$f" ]]; then
        continue
    fi

    # example file names:
    #  - openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
    #  - openshift-client-mac-4.3.0-0.nightly-2019-12-06-161135.tar.gz
    #  - openshift-install-mac-4.3.0-0.nightly-2019-12-06-161135.tar.gz
    #  - openshift-client-linux-4.1.9.tar.gz
    #  - openshift-install-mac-4.3.0-0.nightly-s390x-2020-01-06-081137.tar.gz
    #  ...
    # So, match, and store in a group, any non-digit up to the point we find -DIGIT. Ignore everything else
    # until we match (and store in a group) one of the valid file extensions.
    if [[ "$f" =~ ^([^0-9]+)-[0-9].*(tar.gz|tgz|bz|zip)$ ]]; then
        # Create a symlink like openshift-client-linux.tgz => openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
        ln -sfn "$f" "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
    fi
done
    ''')

    if (major == 4 && minor < 6) {
        echo "Will not extract opm for releases prior to 4.6."
    } else {
        withEnv(["OUTDIR=$CLIENT_MIRROR_DIR", "PULL_SPEC=${quay_url}:${from_release_tag}", "ARCH=$arch", "VERSION=$release_name"]){
            commonlib.shell('''
function extract_opm() {
    OUTDIR=$1
    mkdir -p "${OUTDIR}"
    until OPERATOR_REGISTRY=$(oc adm release info --image-for operator-registry "$PULL_SPEC"); do sleep 10; done
    # extract opm binaries
    BINARIES=(opm)
    PLATFORMS=(linux)
    if [ "$ARCH" == "x86_64" ]; then  # For x86_64, we have binaries for macOS and Windows
        BINARIES+=(darwin-amd64-opm windows-amd64-opm)
        PLATFORMS+=(mac windows)
    fi

    MAJOR=$(echo "$VERSION" | cut -d . -f 1)
    MINOR=$(echo "$VERSION" | cut -d . -f 2)

    PATH_ARGS=()
    for binary in ${BINARIES[@]}; do
        PATH_ARGS+=(--path "/usr/bin/registry/$binary:$OUTDIR")
    done

    GOTRACEBACK=all oc -v5 image extract --confirm --only-files "${PATH_ARGS[@]}" -- "$OPERATOR_REGISTRY"

    # Compress binaries into tar.gz files and calculate sha256 digests
    pushd "$OUTDIR"
    for idx in ${!BINARIES[@]}; do
        binary=${BINARIES[idx]}
        platform=${PLATFORMS[idx]}
        chmod +x "$binary"
        tar -czvf "opm-$platform-$VERSION.tar.gz" "$binary"
        rm "$binary"
        ln -sf "opm-$platform-$VERSION.tar.gz" "opm-$platform.tar.gz"
        sha256sum "opm-$platform-$VERSION.tar.gz" >> sha256sum.txt
    done
    popd
}
extract_opm "$OUTDIR"
            ''')
        }
    }

    sh "tree $CLIENT_MIRROR_DIR"
    sh "cat $CLIENT_MIRROR_DIR/sha256sum.txt"

    // DO NOT use --delete. We only built a part of openshift-v4 locally and don't want to remove
    // anything on the mirror.
    rsync_cmd = "rsync -avzh --chmod=a+rwx,g-w,o-w -e 'ssh -o StrictHostKeyChecking=no' "+
                " ${BASE_TO_MIRROR_DIR}/ ${MIRROR_HOST}:${MIRROR_V4_BASE_DIR}/ "

    if ( ! params.DRY_RUN ) {
        commonlib.shell(script: rsync_cmd)
        timeout(time: 60, unit: 'MINUTES') {
			mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", "openshift-v4", '-v')
			if (mirror_result.contains("[FAILURE]")) {
				echo(mirror_result)
				error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
			}
        }
    } else {
        echo "Not mirroring; would have run: ${rsync_cmd}"
    }

}

/**
 * Derive an architecture name and private release flag from a CI release tag.
 * e.g.
 *   4.1.0-0.nightly-2019-11-08-213727 will return [x86_64, false]
 *   4.1.0-0.nightly-priv-2019-11-08-213727 will return [x86_64, true]
 *   4.1.0-0.nightly-s390x-2019-11-08-213727 will return [s390x, false]
 *   4.1.0-0.nightly-s390x-priv-2019-11-08-213727 will return [s390x, true]
 */
def getReleaseTagArchPriv(from_release_tag) {
    // 4.1.0-0.nightly-s390x-2019-11-08-213727  ->   [4.1.0, 0.nightly, s390x, 2019, 11, 08, 213727]
    def nameComponents = from_release_tag.split('-')

    if (nameComponents.length < 3) {
        // Caller provided something like '4.6.0-rc.4' or 4.6.5.
        // Arch cannot be ascertained.
        return [params.ARCH, false]
    }

    def arch = "x86_64"
    def priv = false
    if (nameComponents[2] == "priv") {
        priv = true
    } else if (!nameComponents[2].isNumber()) {
        arch = nameComponents[2]
        priv = nameComponents[3] == "priv"
    }
    return [arch, priv]
}

def void sendReleaseCompleteMessage(Map release, int advisoryNumber, String advisoryLiveUrl, String arch = 'x86_64', String releaseStreamName='4-stable', String providerName = 'Red Hat UMB') {

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

def sendPreReleaseMessage(Map release, String releaseStreamName, String providerName = 'Red Hat UMB') {
    timeout(3) {
        def sendResult = sendCIMessage(
            messageProperties:
                """release=${release.name}
                release_stream: ${releaseStreamName}
                product=OpenShift Container Platform
                """,
            messageContent: JsonOutput.toJson(release),
            messageType: 'Custom',
            failOnError: true,
            overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
            providerName: providerName,
        )
        echo 'Message sent.'
        echo "Message ID: ${sendResult.getMessageId()}"
        echo "Message content: ${sendResult.getMessageContent()}"
    }
}

def createAdvisoriesFor(ocpVersion, dry_run=false) {
    build(
        job: "build%2Fadvisories",
        propagate: false,
        parameters: [
            string(name: "VERSION", value: ocpVersion),
            string(name: "DATE",    value: determineNextReleaseDate(ocpVersion)),
            string(name: "IMPETUS", value: "standard"),
            booleanParam(name: "DRY_RUN", value: dry_run),
        ]
    )
}

def determineNextReleaseDate(ocpVersion) {
    def dayOfWeek
    switch(ocpVersion) {
        case "4.5":
            dayOfWeek = DayOfWeek.MONDAY
            break
        case "4.4":
            dayOfWeek = DayOfWeek.TUESDAY
            break
        default:
            dayOfWeek = DayOfWeek.WEDNESDAY
            break
    }
    return (
        LocalDate.now()
        .with(TemporalAdjusters.next(DayOfWeek.SUNDAY))     // assuming we don't work on weekends ;D
        .with(TemporalAdjusters.next(dayOfWeek))
        .with(TemporalAdjusters.next(dayOfWeek))            // 2 weeks from now
        .format(DateTimeFormatter.ofPattern("yyyy-MMM-dd")) // format required by elliott
    )
}

def signArtifacts(Map signingParams) {
    build(
        job: "/signing-jobs/signing%2Fsign-artifacts",
        propagate: true,
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

def isSupportEUS(String ocpVersion) {
  return ocpVersion in commonlib.eusVersions
}

/**
 * Opens a series of PRs against the cincinnati-graph-data GitHub repository.
 *    Specifically, a PR for each channel prefix (e.g. candidate, fast, stable) associated with the specified release
 *    and the next minor channels (major.minor+1) IFF those channels currently exist.
 * @param releaseName The name of the release (e.g. "4.3.6")
 * @param advisory The internal advisory number in errata tool. Specify -1 if there is no advisory (e.g. hotfix or rc).
 * @param candidate_only Only open PR for candidate; there is no advisory
 * @param ghorg For testing purposes, you can call this method specifying a personal github org/account. The
 *        openshift-bot must be a contributor in your fork of cincinnati-graph-data.
 * @param noSlackOutput If true, ota-monitor will not be notified
 */
def openCincinnatiPRs(releaseName, advisory, candidate_only=false, ghorg='openshift', noSlackOutput=false) {
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(releaseName)
    if ( major != 4 ) {
        error("Unable to open PRs for unknown major minor: ${major}.${minor}")
    }
    def internal_errata_url = "https://errata.devel.redhat.com/advisory/${advisory}"
    def minorNext = minor + 1
    boolean isReleaseCandidate = candidate_only

    if ( candidate_only || advisory.toInteger() <= 0 ) {
        // There is not advisory for this release
        internal_errata_url = ''
    }

    sshagent(["openshift-bot"]) {

        // PRs that we open will be tracked in this file.
        prs_file = "prs.txt"
        sh "rm -f ${prs_file} && touch ${prs_file}"  // make sure we start with a clean slate

        sh "git clone git@github.com:${ghorg}/cincinnati-graph-data.git"
        dir('cincinnati-graph-data/channels') {
            def prefixes = [ "candidate", "fast", "stable"]
            if ( major == 4 && minor == 1 ) {
                prefixes = [ "prerelease", "stable"]
            }
            if ( isSupportEUS("${major}.${minor}") ) {
                prefixes = [ "candidate", "fast", "stable", "eus"]
            }

            if (isReleaseCandidate) {
                // Release Candidates never go past candidate
                prefixes = prefixes.subList(0, 1)
            }

            prURLs = [:]  // Will map channel to opened PR
            for ( String prefix : prefixes ) {
                channel = "${prefix}-${major}.${minor}"
                channelFile = "${channel}.yaml"
                upgradeChannel = "${prefix}-${major}.${minorNext}"
                upgradeChannelFile = "${upgradeChannel}.yaml"

                channelYaml = [ name: channel, versions: [] ]
                if (fileExists(channelFile)) {
                    channelYaml = readYaml(file: channelFile)
                } else {
                    // create the channel if it does not already exist
                    writeFile(file: channelFile, text: "name: ${channel}\nversions:\n" )
                }

                /**
                 * @param name - The release name
                 * @param version - a list of versions in a channel
                 * @return Returns true if name or name+<arch> exists in list
                 */
                isInChannel = { name, versions  ->
                    for ( String version : versions ) {
                        if ( version.startsWith( name + "+") || version.equals(name) ) {
                            return true
                        }
                    }
                    return false
                }

                addToChannel = !isInChannel(releaseName, channelYaml.get('versions', []))

                upgradeChannelYaml = [ name: upgradeChannel, versions: [] ]
                addToUpgradeChannel = false
                releasesForUpgradeChannel = []
                if ( internal_errata_url || isReleaseCandidate ) {
                    if (fileExists(upgradeChannelFile)) {
                        upgradeChannelYaml = readYaml(file: upgradeChannelFile)
                        upgradeChannelVersions = upgradeChannelYaml.get('versions', [])

                        // at least one version must be present & make sure that releaseName is not already there
                        if ( upgradeChannelVersions && !isInChannel(releaseName, upgradeChannelVersions) ) {
                            releasesForUpgradeChannel = [ releaseName ]
                            addToUpgradeChannel = true
                        }
                    }
                } else {
                    // This is just a tactical release for a given customer (e.g. promoting a nightly).
                    // There should no upgrade path encouraged for it.
                }

                echo "Creating PR for ${prefix} channel(s)"
                branchName = "pr-${prefix}-${releaseName}"
                pr_title = "Enable ${releaseName} in ${prefix} channel(s)"

                labelArgs = ''
                extraSlackComment = ''

                pr_messages = [ pr_title ]

                if ( internal_errata_url ) {
                    switch(prefix) {
                        case 'prerelease':
                        case 'candidate':
                            pr_messages << "Please merge immediately. This PR does not need to wait for an advisory to ship, but the associated advisory is ${internal_errata_url} ."
                            labelArgs = "-l 'lgtm,approved'"
                            extraSlackComment = "automatically approved"
                            break
                        case 'fast':
                            pr_messages << "Please merge as soon as ${internal_errata_url} is shipped live OR if a Cincinnati-first release is approved."
                            if (prURLs.containsKey('candidate')) {
                                pr_messages << "This should provide adequate soak time for candidate channel PR ${prURLs.candidate}"
                            }
                            // For non-candidate, put a hold on the PR to prevent accidental merging
                            labelArgs = "-l 'do-not-merge/hold'"
                            break
                        case 'stable':
                            // For non-candidate, put a hold on the PR to prevent accidental merging
                            labelArgs = "-l 'do-not-merge/hold'"
                            pr_messages << "Please merge within 48 hours of ${internal_errata_url} shipping live OR a Cincinnati-first release."

                            if (prURLs.containsKey('prerelease')) {
                                pr_messages << "This should provide adequate soak time for prerelease channel PR ${prURLs.prerelease}"
                            }
                            if (prURLs.containsKey('fast')) {
                                pr_messages << "This should provide adequate soak time for fast channel PR ${prURLs.fast}"
                            }

                            break
                        case 'eus':
                            // currently put eus change in a seperate PR as same as stable channel
                            labelArgs = "-l 'do-not-merge/hold'"
                            pr_messages << "Please merge within 48 hours of ${internal_errata_url} shipping live OR a Cincinnati-first release."

                            if (prURLs.containsKey('fast')) {
                                pr_messages << "This should provide adequate soak time for fast channel PR ${prURLs.fast}"
                            }

                            break
                        default:
                            error("Unknown prefix: ${prefix}")
                    }
                } else {  // merge non-GA release PRs immediately
                    labelArgs = "-l 'lgtm,approved'"
                    if ( isReleaseCandidate ) {
                        // Errata is irrelevant for release candidate.
                        pr_messages << "This is a release candidate. There is no advisory associated."
                        pr_messages << 'Please merge immediately.'
                    } else {
                        pr_messages << "Promoting a hotfix release (e.g. for a single customer). There is no advisory associated."
                        pr_messages << 'Please merge immediately.'
                    }
                }

                if ( addToUpgradeChannel ) {
                    pr_messages << "This PR will also enable upgrades from ${releaseName} to releases in ${upgradeChannel}"
                }

                if ( !addToChannel && !addToUpgradeChannel ) {
                    def pr_info = "No Cincinnati PRs opened for ${prefix}. Might have been done by previous architecture's release build.\n"
                    echo pr_info
                    currentBuild.description += pr_info
                    continue
                }

                withCredentials([string(credentialsId: 'openshift-bot-token', variable: 'access_token')]) {
                    def messageArgs = ''
                    for ( String msg : pr_messages ) {
                        messageArgs += "--message '${msg}' "
                    }

                    sh """
                        set -euo pipefail
                        set -o xtrace
                        if git checkout origin/${branchName} ; then
                            echo "The branch ${branchName} already exists in cincinnati-graph-data. No additional PRs will be created."
                            exit 0
                        fi
                        git branch -f ${branchName} origin/master
                        git checkout ${branchName}
                        if [[ "${addToChannel}" == "true" ]]; then
                            echo >> ${channelFile}    # add newline to avoid if human has added something without newline
                            echo '- ${releaseName}' >> ${channelFile}   # add the entry
                            git add ${channelFile}
                        fi
                        if [[ "${addToUpgradeChannel}" == "true" ]]; then
                            # We want to insert the previous minors right after versions: so they stay above other entries.
                            # Why not set it in right before the next minor begins? Because we don't confuse a comment line that might exist above the next minor.
                            # First, create a file with the content we want to insert
                            echo -n > ul.txt  # Clear from previous channels
                            for urn in ${releasesForUpgradeChannel.join(' ')} ; do
                                echo "- \$urn" >> ul.txt  # add the entry to lines to insert
                            done
                            echo >> ul.txt
                            rm -f slice*  # Remove any files from previous csplit runs
                            csplit ${upgradeChannelFile} '/versions:/+1' --prefix slice   # create slice00 (up to and including versions:) and slice01 (everything after)
                            cat slice00 ul.txt slice01 > ${upgradeChannelFile}
                            git add ${upgradeChannelFile}
                        fi
                        git commit -m "${pr_title}"
                        git push -u origin ${branchName}
                        export GITHUB_TOKEN=${access_token}
                        hub pull-request -b ${ghorg}:master ${labelArgs} -h ${ghorg}:${branchName} ${messageArgs} > ${prefix}.pr
                        cat ${prefix}.pr >> ${prs_file}    # Aggregate all PRs
                        if test -n "${extraSlackComment}"; then
                            echo "${extraSlackComment}" >> "${prs_file}"
                        fi
                        """

                    prURLs[prefix] = readFile("${prefix}.pr").trim()
                }
            }

            def prs = readFile(prs_file).trim()
            if ( prs ) {  // did we open any?
                def slack_msg = "ART has opened Cincinnati PRs for ${releaseName}:\n${prs}"
                slack_msg += "\n@patch-manager ${major}.${minor}.z merge window is open for next week."
                if ( ghorg == 'openshift' && !noSlackOutput) {
                    slacklib.to('#forum-release').say(slack_msg)
                } else {
                    echo "Would have sent the following slack notification to #forum-release"
                    echo slack_msg
                }
            }

        }
    }
}

return this

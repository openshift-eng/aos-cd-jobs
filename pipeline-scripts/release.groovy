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

def getArchPrivSuffix(arch, priv) {
    def suffix = commonlib.goSuffixForArch(arch)  // expect golang in release-controller land
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

    def (arch, priv) = from_release_tag ? getReleaseTagArchPriv(from_release_tag) : [params.ARCH, false]

    echo "Generating release payload"
    echo "CI release name: ${from_release_tag}"
    echo "Calculated arch: ${arch}"
    echo "Private: ${priv}"

    def suffix = getArchPrivSuffix(arch, priv)
    def publicSuffix = getArchPrivSuffix(arch, false)

    // build oc command
    def cmd = "GOTRACEBACK=all oc adm release new "
    cmd += "-n ocp${publicSuffix} "
    if (from_release_tag) {
        cmd += "--from-release=registry.ci.openshift.org/ocp${suffix}/release${suffix}:${from_release_tag} "
    } else {
        cmd += "--reference-mode=source --from-image-stream ${params.VERSION}-art-assembly-${params.ASSEMBLY}${publicSuffix} "
    }
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

    stdout = buildlib.withAppCiAsArtPublish() {
        cmd += " --kubeconfig ${KUBECONFIG}"
        return commonlib.shell(
            script: cmd,
            returnStdout: true
        )
    }

    payloadDigest = parseOcpRelease(stdout)

    currentBuild.description += " ${payloadDigest}"
}

def getPayloadDigest(quay_url, release_tag) {
    def payloadInfo = buildlib.withAppCiAsArtPublish() {
        def cmd = "GOTRACEBACK=all oc --kubeconfig ${KUBECONFIG} adm release info ${quay_url}:${release_tag} -o json"
        def stdout = commonlib.shell(
            script: cmd,
            returnStdout: true
        )
        return readJSON(text: stdout)
    }
    return payloadInfo['digest']
}

def getAdvisories(String group) {
    def yamlStr = buildlib.doozer("--group ${group} config:read-group advisories --yaml", [capture: true])
    def yamlData = readYaml text: yamlStr
    return yamlData
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
    def cmd = "GOTRACEBACK=all oc tag ${quay_url}:${release_tag} ocp${publicSuffix}/release${publicSuffix}:${release_name}"

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return
    }

    buildlib.withAppCiAsArtPublish() {
        cmd += " --kubeconfig ${KUBECONFIG}"
        commonlib.shell(
            script: cmd
        )
    }
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
        script: "elliott -g ${group} find-bugs:blocker"
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

def validateInFlightPrevVersion(in_flight_prev, major, prevMinor) {
    pattern = /$major\.$prevMinor\.(\d+)/
    match = in_flight_prev =~ pattern
    match.find()
    if (match.size() == 1) {
        return true
    }
    return false
}

def stageGetReleaseInfo(quay_url, release_tag){
    def cmd = "GOTRACEBACK=all oc adm release info --pullspecs ${quay_url}:${release_tag}"

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return "Dry Run - No Info"
    }

    def res = buildlib.withAppCiAsArtPublish() {
        cmd += " --kubeconfig ${KUBECONFIG}"
        return commonlib.shell(
            returnAll: true,
            script: cmd
        )
    }

    if (res.returnStatus != 0){
        error(res.stderr)
    }

    return res.stdout.trim()
}

def stagePublishMultiClient(quay_url, from_release_tag, release_name, client_type) {
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(release_name)

    // Anything under this directory will be sync'd to the mirror
    def BASE_TO_MIRROR_DIR="${WORKSPACE}/to_mirror/openshift-v4"
    def RELEASE_MIRROR_DIR="${BASE_TO_MIRROR_DIR}/multi/clients/${client_type}/${release_name}"
    sh "rm -rf ${BASE_TO_MIRROR_DIR}"

    for (subarch in commonlib.goArches) {
        if ( subarch == "multi" ) {
            continue
        }

        // From the newly built release, extract the client tools into the workspace following the directory structure
        // we expect to publish to mirror
        def CLIENT_MIRROR_DIR="${RELEASE_MIRROR_DIR}/${subarch}"
        def go_subarch = commonlib.goArchForBrewArch(subarch)
        sh "mkdir -p ${CLIENT_MIRROR_DIR}"

        def tools_extract_cmd = "MOBY_DISABLE_PIGZ=true GOTRACEBACK=all oc adm release extract --tools --command-os='*' -n ocp " +
                                    " --filter-by-os=${subarch} --to=${CLIENT_MIRROR_DIR} --from ${quay_url}:${from_release_tag}"

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
        # So, match, and store in a group, any character up to the point we find -DIGIT. Ignore everything else
        # until we match (and store in a group) one of the valid file extensions.
        if [[ "$f" =~ ^([^-]+)((-[^0-9][^-]+)+)-[0-9].*(tar.gz|tgz|bz|zip)$ ]]; then
            # Create a symlink like openshift-client-linux.tgz => openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
            ln -sfn "$f" "${BASH_REMATCH[1]}${BASH_REMATCH[2]}.${BASH_REMATCH[4]}"
        fi
    done
        ''')

        sh "tree $CLIENT_MIRROR_DIR"
        sh "cat $CLIENT_MIRROR_DIR/sha256sum.txt"
    }

    // Create a master sha256sum.txt including the sha256sum.txt files from all subarches
    // This is the file we will sign -- trust is transitive to the subarches
    commonlib.shell(script: """
    # change directories so that entries in sha256sum entries are relative subarch dirs and not absolute
    cd ${RELEASE_MIRROR_DIR}
    sha256sum */sha256sum.txt > ${RELEASE_MIRROR_DIR}/sha256sum.txt
    """)

    def mirror_cmd = "aws s3 sync --no-progress --exact-timestamps ${BASE_TO_MIRROR_DIR}/ s3://art-srv-enterprise/pub/openshift-v4/"
    if ( ! params.DRY_RUN ) {
        // Publish the clients to our S3 bucket.
        try {
            withCredentials([
            file(credentialsId: 'aws-credentials-file', variable: 'AWS_SHARED_CREDENTIALS_FILE'),
            string(credentialsId: 's3-art-srv-enterprise-cloudflare-endpoint', variable: 'CLOUDFLARE_ENDPOINT')]) {
                commonlib.shell(script: mirror_cmd)
                commonlib.shell(script: "${mirror_cmd} --profile cloudflare --endpoint-url ${env.CLOUDFLARE_ENDPOINT}")
            }
        } catch (ex) {
            slacklib.to("#art-release").say("Failed syncing OCP clients to S3 in ${currentBuild.displayName} (${env.JOB_URL})")
        }

    } else {
        echo "Not mirroring; would have run: ${mirror_cmd}"
    }


}

def stagePublishClient(quay_url, from_release_tag, release_name, arch, client_type) {
    def (major, minor) = commonlib.extractMajorMinorVersionNumbers(release_name)

    // Anything under this directory will be sync'd to the mirror
    def BASE_TO_MIRROR_DIR="${WORKSPACE}/to_mirror/openshift-v4"
    sh "rm -rf ${BASE_TO_MIRROR_DIR}"

    // From the newly built release, extract the client tools into the workspace following the directory structure
    // we expect to publish to mirror
    def CLIENT_MIRROR_DIR="${BASE_TO_MIRROR_DIR}/${arch}/clients/${client_type}/${release_name}"
    sh "mkdir -p ${CLIENT_MIRROR_DIR}"

    def tools_extract_cmd = "MOBY_DISABLE_PIGZ=true GOTRACEBACK=all oc adm release extract --tools --command-os='*' -n ocp " +
                                " --to=${CLIENT_MIRROR_DIR} --from ${quay_url}:${from_release_tag}"
    commonlib.shell(script: tools_extract_cmd)

    if ( arch == 'x86_64' ) {
        // oc_mirror_extract_cmd needs to extract to a emtpy folder, since tools_extract_cmd is already extracting to
        // CLIENT_MIRROR_DIR, creating a temporary folder
        def TEMP_OC_MIRROR_DIR = "${CLIENT_MIRROR_DIR}/temp-oc-mirror-dir"
        sh "mkdir ${TEMP_OC_MIRROR_DIR}"

        // oc image  extract requires an empty destination directory. So do this before extracting tools.
        // oc adm release extract --tools does not require an empty directory, but will overwrite the files.
        def oc_mirror_extract_cmd = '''
            # If the release payload contains an oc-mirror artifact image, then extract the oc-mirror binary.
            if oc adm release info ${QUAY_URL}:${FROM_RELEASE_TAG} --image-for=oc-mirror ; then
                MOBY_DISABLE_PIGZ=true GOTRACEBACK=all oc image extract `oc adm release info ${QUAY_URL}:${FROM_RELEASE_TAG} --image-for=oc-mirror` --path /usr/bin/oc-mirror:${TEMP_OC_MIRROR_DIR}
                pushd ${TEMP_OC_MIRROR_DIR}
                tar zcvf oc-mirror.tar.gz oc-mirror
                popd
                pushd ${CLIENT_MIRROR_DIR}
                cp ${TEMP_OC_MIRROR_DIR}/oc-mirror.tar.gz oc-mirror.tar.gz
                sha256sum oc-mirror.tar.gz >> sha256sum.txt
                popd
                rm -rf ${TEMP_OC_MIRROR_DIR}
            fi
        '''
        withEnv(["CLIENT_MIRROR_DIR=${CLIENT_MIRROR_DIR}", "QUAY_URL=${quay_url}", "FROM_RELEASE_TAG=${from_release_tag}", "TEMP_OC_MIRROR_DIR=${TEMP_OC_MIRROR_DIR}"]) {
            commonlib.shell(script: oc_mirror_extract_cmd)
        }
    }


    // Find the GitHub commit id for cli, installer and opm and download the repo at that commit, then publish it.
    def download_tarballs = '''
        for image_name in cli installer operator-registry; do
          # Get the image digest
          image_digest=$(oc adm release info ${QUAY_URL}:${FROM_RELEASE_TAG} --image-for=${image_name})

          # If it exists
          if [[ ${image_digest} ]] ; then
            # Store the image info in a temporary file
            oc image info --output json "$image_digest" > temp_image_info.json

            # Get the commit SHA, GitHub url of the source and extract the name
            commit=$( cat temp_image_info.json | jq -r '.config.config.Labels."io.openshift.build.commit.id"')
            source_url=$( cat temp_image_info.json | jq -r '.config.config.Labels."io.openshift.build.source-location"')
            source_name=$( echo "$source_url" | cut -d '/' -f 5)

            case $source_name in
              oc)
                source_name="openshift-client"
                ;;
              installer)
                source_name="openshift-install"
                ;;
              operator-framework-olm)
                source_name="opm"
                ;;
            esac

            # Delete temporary file
            rm temp_image_info.json

            # Download the tar file to the correct path
            pushd ${CLIENT_MIRROR_DIR}
                curl -L -o "${source_name}-src-${FROM_RELEASE_TAG}.tar.gz" "${source_url}/archive/${commit}.tar.gz"
                sha256sum "${source_name}-src-${FROM_RELEASE_TAG}.tar.gz" >> sha256sum.txt
            popd
          fi
        done
    '''
    // Injecting variables directly as env so as to not confuse groovy and bash string interpolation
    withEnv(["CLIENT_MIRROR_DIR=${CLIENT_MIRROR_DIR}", "QUAY_URL=${quay_url}", "FROM_RELEASE_TAG=${from_release_tag}"]) {
            commonlib.shell(script: download_tarballs)
    }

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
    # So, match, and store in a group, any character up to the point we find -DIGIT. Ignore everything else
    # until we match (and store in a group) one of the valid file extensions.
    if [[ "$f" =~ ^([^-]+)((-[^0-9][^-]+)+)-[0-9].*(tar.gz|tgz|bz|zip)$ ]]; then
        # Create a symlink like openshift-client-linux.tgz => openshift-client-linux-4.3.0-0.nightly-2019-12-06-161135.tar.gz
        ln -sfn "$f" "${BASH_REMATCH[1]}${BASH_REMATCH[2]}.${BASH_REMATCH[4]}"
    fi
done
    ''')

    if ( minor > 0 ) {
        try {
            // To encourage customers to explore dev-previews & pre-GA releases, populate changelog
            // https://issues.redhat.com/browse/ART-3040
            prevMinor = minor - 1
            rcURL = commonlib.getReleaseControllerURL(release_name)
            rcArch = commonlib.getReleaseControllerArch(release_name)
            stableStream = (rcArch=="amd64")?"4-stable":"4-stable-${rcArch}"
            outputDest = "${CLIENT_MIRROR_DIR}/changelog.html"
            outputDestMd = "${CLIENT_MIRROR_DIR}/changelog.md"

            // If the previous minor is not yet GA, look for the latest fc/rc/ec. If the previous minor is GA, this should
            // always return 4.m.0.
            prevGA = commonlib.shell(returnStdout: true, script:"curl -s -X GET -G https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/4-stable/latest --data-urlencode 'in=>4.${prevMinor}.0-0 <4.${prevMinor}.1' | jq -r .name").trim()

            // See if the previous minor has GA'd yet; e.g. https://amd64.ocp.releases.ci.openshift.org/releasestream/4-stable/release/4.8.0
            def check = httpRequest(
                url: "${rcURL}/releasestream/${stableStream}/release/${prevGA}",
                httpMode: 'GET',
                validResponseCodes: '200,404',  // if we get 404, do not compute changelog yet; prev has not GA'd.
                timeout: 30,
            )
            if (check.status == 200) {
                // If prevGA is known to the release controller, compute the changelog html
                def response = httpRequest(
                    url: "${rcURL}/changelog?from=${prevGA}&to=${release_name}&format=html",
                    httpMode: 'GET',
                    timeout: 180,
                )
                writeFile(file: outputDest, text: response.content)

                // Also collect the output in markdown for SD to consume
                response = httpRequest(
                    url: "${rcURL}/changelog?from=${prevGA}&to=${release_name}",
                    httpMode: 'GET',
                    timeout: 180,
                )
                writeFile(file: outputDestMd, text: response.content)
            } else {
                writeFile(file: outputDest, text: "<html><body><p>Changelog information cannot be computed for this release. Changelog information will be populated for new releases once ${prevGA} is officially released.</p></body></html>")
                writeFile(file: outputDestMd, text: "Changelog information cannot be computed for this release. Changelog information will be populated for new releases once ${prevGA} is officially released.")
            }
        } catch (clex) {
            slacklib.to(release_name).failure("Error generating changelog for release", clex)
        }
    }

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

    GOTRACEBACK=all oc -v4 image extract --confirm --only-files "${PATH_ARGS[@]}" -- "$OPERATOR_REGISTRY"

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

    sh "tree $CLIENT_MIRROR_DIR"
    sh "cat $CLIENT_MIRROR_DIR/sha256sum.txt"

    mirror_cmd = "aws s3 sync --no-progress --exact-timestamps ${BASE_TO_MIRROR_DIR}/ s3://art-srv-enterprise/pub/openshift-v4/"
    if ( ! params.DRY_RUN ) {
        // Publish the clients to our S3 bucket.
        try {
            withCredentials([
            file(credentialsId: 'aws-credentials-file', variable: 'AWS_SHARED_CREDENTIALS_FILE'),
            string(credentialsId: 's3-art-srv-enterprise-cloudflare-endpoint', variable: 'CLOUDFLARE_ENDPOINT')]) {
                commonlib.shell(script: mirror_cmd)
                commonlib.shell(script: "${mirror_cmd} --profile cloudflare --endpoint-url ${env.CLOUDFLARE_ENDPOINT}")
            }
        } catch (ex) {
            slacklib.to("#art-release").say("Failed syncing OCP clients to S3 in ${currentBuild.displayName} (${env.JOB_URL})")
        }

    } else {
        echo "Not mirroring; would have run: ${mirror_cmd}"
    }

}

/**
 * Derive an architecture name and private flag from a release registry repo tag.
 * e.g.
 *   4.1.0-0.nightly-2019-11-08-213727 will return [x86_64, false]
 *   4.1.0-0.nightly-priv-2019-11-08-213727 will return [x86_64, true]
 *   4.1.0-0.nightly-s390x-2019-11-08-213727 will return [s390x, false]
 *   4.1.0-0.nightly-s390x-priv-2019-11-08-213727 will return [s390x, true]
 *   4.9.0-0.nightly-arm64-priv-2021-06-08-213727 will return [aarch64, true]
 *   Should also work for stable tags like:
 *   4.10.42-x86_64       returns [x86_64, false]
 *   4.12.0-ec.2-aarch64  returns [aarch64, false]
 *   And even release names (should be no repo tags like this) like:
 *   4.10.42              returns [params.ARCH || x86_64, false]
 *   4.12.0-ec.2          returns [params.ARCH || x86_64, false]
 */
def getReleaseTagArchPriv(from_release_tag) {
    def nameComponents = from_release_tag.split('-')
    // 4.1.0-0.nightly-s390x-2019-11-08-213727  ->   [4.1.0, 0.nightly, s390x, 2019, 11, 08, 213727]

    def priv = "priv" in nameComponents
    def arch = "auto"
    if ( params.ARCH ) {
        arch = params.ARCH
    }
    for (arch_cmp in commonlib.goArches + commonlib.brewArches)
        if (arch_cmp in nameComponents)
            arch = commonlib.brewArchForGoArch(arch_cmp)
    if (arch == "auto" || !arch)
        arch = "x86_64"  // original default before arches were specified
    return [arch, priv]
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

return this

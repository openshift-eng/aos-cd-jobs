buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

oc_cmd = "oc --config=/home/jenkins/kubeconfigs/art-publish.kubeconfig"

// dump important tool versions to console
def stageVersions() {
    sh "oc version"
    sh "doozer --version"
    sh "elliott --version"
}

def stageValidation(quay_url) {
    echo "Verifying payload does not already exist"
    res = commonlib.shell(
            returnAll: true,
            script: "GOTRACEBACK=all ${oc_cmd} adm release info ${quay_url}:${params.NAME}"
    )

    if(res.returnStatus == 0){
        error("Payload ${params.NAME} already exists! Cannot continue.")
    }

    // AMH - This may be optional?
    if (params.ADVISORY != "") {
        echo "Verifying advisory exists"
        res = commonlib.shell(
                returnAll: true,
                script: "elliott get ${params.ADVISORY}"
        )

        if(res.returnStatus != 0){
            error("Advisory ${params.ADVISORY} does not exist! Cannot continue.")
        }
    }
}

def stageGenPayload(quay_url) {
    // build metadata blob
    def metadata = "{\"description\": \"${params.DESCRIPTION}\""
    if (params.ERRATA_URL != "") {
        metadata += ", \"url\": \"${params.ERRATA_URL}\""
    }
    metadata += "}"

    // build oc command
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release new "
    cmd += "--from-release=registry.svc.ci.openshift.org/ocp/release:${params.FROM_RELEASE_TAG} "
    if (params.PREVIOUS != "") {
        cmd += "--previous \"${params.PREVIOUS}\" "
    }
    cmd += "--name ${params.NAME} "
    cmd += "--metadata '${metadata}' "
    cmd += "--to-image=${quay_url}:${params.NAME} "

    if (params.DRY_RUN){
        cmd += "--dry-run=true "
    }

    commonlib.shell(
            script: cmd
    )
}

def stageTagRelease(quay_url) {
    def name = params.NAME
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
def stageWaitForStable() {
    def count = 0
    def stream = "https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/4-stable/latest"
    def cmd = "curl -H 'Cache-Control: no-cache' ${stream} | jq -r '.name'"
    def stable = ""

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return
    }

    // 2019-05-23 - As of now jobs will not be tagged as `Accepted`
    // until they pass an upgrade test, hence the 2 hour wait loop
    while (count < 24) { // wait for 5m * 24 = 120m = 2 hours
        def res = commonlib.shell(
                returnAll: true,
                script: cmd
        )

        if (res.returnStatus != 0){
            echo "Error fetching latest stable: ${res.stderr}"
        }
        else {
            stable = res.stdout.trim()
            echo "${stable}"
            // found, move on
            if (stable == params.NAME){ return }
        }

        count++
        sleep(300) //wait for 5 minutes between tries
    }

    if (stable != params.NAME){
        error("Stable release has not updated to ${params.NAME} in the allotted time. Aborting.")
    }
}

def stageGetReleaseInfo(quay_url){
    def cmd = "GOTRACEBACK=all ${oc_cmd} adm release info --pullspecs ${quay_url}:${params.NAME}"

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
                    buildlib.param('String', 'STREAM', stream, 'String', 'PATH', path)
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

return this

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

oc_cmd = "oc --config=/home/jenkins/kubeconfigs/art-publish.kubeconfig"

// dump important tool versions to console
def stageVersions() {
    sh "oc version"
    sh "doozer --version"
    sh "elliott --version"
}

def stageValidation() {
    echo "Verifying payload does not already exist"
    res = commonlib.shell(
        returnAll: true,
        script: "${oc_cmd} adm release info ${params.NAME}"
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

def stageGenPayload() {
    // build metadata blob
    def metadata = "{\"description\": \"${params.DESCRIPTION}\""
    if (params.ADVISORY != "") {
        metadata += ", \"advisory_url\": \"https://errata.devel.redhat.com/advisory/${params.ADVISORY}\""
    }
    metadata += "}"

    // build oc command
    def cmd = "${oc_cmd} adm release new "
    cmd += "--from-release=registry.svc.ci.openshift.org/ocp/release:${params.FROM_RELEASE_TAG} "
    cmd += "--name ${params.NAME} "
    cmd += "--metadata '${metadata}' "
    cmd += "--to-image=quay.io/openshift-release-dev/ocp-release:${params.NAME} "

    if (params.DRY_RUN){
        cmd += "--dry-run=true "
    }

    commonlib.shell(
        script: cmd
    )
}

def stageTagStable() {
    def name = params.NAME
    def cmd = "${oc_cmd} tag quay.io/openshift-release-dev/ocp-release:${name} ocp/release:${name}"

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return
    }

    commonlib.shell(
        script: cmd
    )
}

def stageWaitForStable() {
    def count = 0
    def stream = "https://openshift-release.svc.ci.openshift.org/api/v1/releasestream/4-stable/latest"
    def cmd = "curl -H 'Cache-Control: no-cache' ${stream} | jq -r '.name'"
    def stable = ""

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return
    }

    // New build may take a while to show up
    // Check every minute until it does or 30 minutes hit
    while (count < 30) { // wait for 30 minutes
        def res = commonlib.shell(
            returnAll: true,
            script: cmd
        )

        if(res.rc != 0){
            echo "Error fetching latest stable: ${res.stderr}"
        }
        else {
            stable = res.stdout.trim()
            echo "${stable}"
            // found, move on
            if (stable == params.NAME){ return }
        }

        count++
        sleep(60) //wait for 60 seconds between tries
    }

    if (stable != params.NAME){
        error("Stable release has not updated to ${params.NAME} in the allotted time. Aborting.")
    }
}

def stageGetReleaseInfo(){
    def cmd = "${oc_cmd} adm release info --pullspecs quay.io/openshift-release-dev/ocp-release:${params.NAME}"

    if (params.DRY_RUN) {
        echo "Would have run \n ${cmd}"
        return "Dry Run - No Info"
    }

    def res = commonlib.shell(
            returnAll: true,
            script: cmd
    )

    if (res.rc != 0){
        error(res.stderr)
    }

    return res.stdout.trim()
}

def stageClientSync() {
    if (params.DRY_RUN) {
        echo "Would have run oc_sync job"
        return
    }

    build(
        job: 'build%2Foc_sync',
        parameters: [
            buildlib.param('String', 'STREAM', '4-stable')
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
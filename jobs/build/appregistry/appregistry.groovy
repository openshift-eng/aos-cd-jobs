buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
workDir = null
buildVersion = null

def initialize(workDir) {
    this.workDir = workDir
    this.buildVersion = params.BUILD_VERSION
    buildlib.initialize(false)
    buildlib.cleanWorkdir(workDir)
}

/*
    Turn lines from doozer that look like:
        label,distgit,nvr,component
    into maps with these fields:
        distgit: "foo-operator"
        component: "foo-operator-container"
        nvr: "foo-operator-container-v4.3.0-12345" (latest build of this component)
    Keep those that have the appregistry label.
*/ 
@NonCPS
def parseAndFilterOperators(lines) {
    def data = []
    lines.split().each { line ->
        // label, distgit, component, nvr
        def fields = line.split(',')
        if (fields[0]) {
            data.add([
                distgit: fields[1],
                component: fields[2],
                nvr: fields[3],
            ])
        }
    }
    return data
}

/*
    Use login credentials from Jenkins to generate a temporary token that we can
    use to submit requests to OMPS for publishing metadata to the dev appregistry.
    Returns: the token. Otherwise raises an error.
*/
def retrieveBotToken() {
    def token = ""
    withCredentials([usernamePassword(
        credentialsId: 'quay_appregistry_omps_bot',
        usernameVariable: 'QUAY_USERNAME',
        passwordVariable: 'QUAY_PASSWORD',
    )]) {
        def requestJson = """
        {
            "user": {
                "username": "${QUAY_USERNAME}",
                "password": "${QUAY_PASSWORD}"
            }
        }
        """
        retry(3) {
            def response = httpRequest(
                url: "https://quay.io/cnr/api/v1/users/login",
                httpMode: 'POST',
                contentType: 'APPLICATION_JSON',
                requestBody: requestJson,
                timeout: 60,
                // we want to know what the response was even on failure,
                // and we only get that if this doesn't raise an error:
                validResponseCodes: "200:599",
            )
            if (response.status != 200) {
                sleep(5)
                error "Quay token request failed: ${response.status} ${response.content}"
            }
            token = readJSON(text: response.content).token
        }
    }
    return token
}

// validate job parameters
def validate(params) {
    if (params.STREAM in ["stage", "prod"]) {
        if (!params.OLM_OPERATOR_ADVISORIES || !params.METADATA_ADVISORY) {
            currentBuild.description += """\n
            ERROR: OLM_OPERATOR_ADVISORIES and METADATA_ADVISORY parameters are required for selected STREAM.
            """
            return false
        }
    }
    return true
}

def doozer(cmd) {
    buildlib.doozer("--working-dir ${workDir} -g openshift-${buildVersion} ${cmd}", [capture: true])
}

def elliott(cmd) {
    buildlib.elliott("-g openshift-${buildVersion} ${cmd}", [capture: true])
}

/*
    request dockerfile information for image configs from doozer
    param limitImages: optional distgit names to limit the query
    returns: lines of output with the desired information per image
*/
def getImagesData(limitImages) {
    if (limitImages) {
        limitImages = "--images " + commonlib.cleanCommaList(limitImages)
    }
    doozer """
        ${limitImages}
        images:print
        --label 'com.redhat.delivery.appregistry'
        --short '{label},{name},{component},{build}'
    """
}

/*
    List all the builds attached to given advisories.
    param advisories (string): advisory numbers to search
    returns: a list of NVR strings
*/
def fetchNVRsFromAdvisories(advisories) {
    commonlib.cleanCommaList(advisories).split(",").collect { advisory ->
        readJSON(text: elliott("get --json - ${advisory}")).errata_builds.values().flatten()
    }.flatten()
}

/*
    Find the image builds from the advisories that correspond to the operator image configs doozer found.
    param images: a list of image maps, each like [distgit: "foo", component: "foo-container", ...]
    param advisoriesNVRs: a list of NVRs like "foo-container-4.2-123456"
    return: the same list of maps, each with nvr replaced by an advisory nvr (or null)
*/
def findImageNVRsInAdvisories(images, advisoriesNVRs) {
    images.collect {
        image -> image + [nvr: advisoriesNVRs.find { it.startsWith(image.component) }]
    }
}

/*
    Post an NVR to OMPS (Operator Manifest Push Service) for publication to redhat-operators-art appregistry
    param token: temporary auth token for publishing to quay
    param metadata_nvr: NVR of the metadata container we want to push
    returns: the http response object
*/
def pushToOMPS(token, metadata_nvr) {
    httpRequest(
        url: "https://omps-prod.cloud.paas.psi.redhat.com/v2/redhat-operators-art/koji/${metadata_nvr}",
        httpMode: 'POST',
        customHeaders: [[name: 'Authorization', value: token]],
        timeout: 60,
        // we want to know what the response was even on failure,
        // and we only get that if this doesn't raise an error:
        validResponseCodes: "200:599",
    )
}

/*
    Have doozer find the latest metadata container build NVRs from given operator container NVRs.
    param operatorNVRs: list of operator container NVRs
    param stream: dev|stage|prod depending on which we are looking for
    returns: a list of metadata container NVRs
*/
def getMetadataNVRs(operatorNVRs, stream) {
    def nvrFlags = operatorNVRs.collect { "--nvr ${it}" }.join(" ")
    return doozer("operator-metadata:latest-build --stream ${stream} ${nvrFlags}").split()
}

// attach to given advisory a list of NVRs 
def attachToAdvisory(advisory, metadata_nvrs) {
    def elliott_build_flags = []
    metadata_nvrs.each { nvr -> elliott_build_flags.add("--build ${nvr}") }

    elliott """
        find-builds -k image
        ${elliott_build_flags.join(" ")}
        --attach ${advisory}
    """
}

/*
    According to job parameters, find out which images (all or limited by param) are operators.
    Find the latest operator builds for which we want metadata containers.
    For stage and prod, use the operator builds that are attached to an advisory.
    Returns a list of maps that have entries like:
        distgit: "foo-operator"
        component: "foo-operator-container"
        nvr: "foo-operator-container-v4.3.0-12345"
*/
def stageFetchOperatorImages() {
    // get the images that are configured to be optional operators
    operatorBuilds = parseAndFilterOperators(getImagesData(params.IMAGES.trim()))

    if (params.STREAM in ["stage", "prod"]) {
        // look up the corresponding container builds that were attached to advisories
        def advisoriesNVRs = fetchNVRsFromAdvisories(params.OLM_OPERATOR_ADVISORIES)
        operatorBuilds = findImageNVRsInAdvisories(operatorBuilds, advisoriesNVRs)

        if (operatorBuilds.any { it.nvr == null }) {
            currentBuild.description += """\n
            Advisories missing operators ${operatorBuilds.findAll { it.nvr }.collect { it.distgit }.join(",")}
            """
            echo """
            ERROR: The following operators were not found in provided advisories.
            ${operatorBuilds.findAll { !it.nvr }.collect { it.distgit }.join(",")}

            Possible solutions:
            1. Add more advisories in OLM_OPERATOR_ADVISORIES parameter, that have the missing operators attached
            2. Attach missing operators to at least one of the provided advisories: ${params.OLM_OPERATOR_ADVISORIES}
            3. Limit the expected operators in IMAGES parameter: ${operatorBuilds.findAll { it.nvr }.collect { it.distgit }.join(",")}
            """
            error "operators not found"
        }
    }
    return operatorBuilds
}

// use doozer to build metadata containers (if needed) for a given stream and list of operator builds
def stageBuildMetadata(operatorBuilds) {
    def nvrs = operatorBuilds.collect { item -> item.nvr }

    doozer """
        operator-metadata:build ${nvrs.join(' ')}
        ${params.FORCE_METADATA_BUILD ? "-f" : ""}
        --stream ${params.STREAM}
    """
}

// wrap pushToOMPS with retries; it fails until the CVP for the container build completes
def pushToOMPSWithRetries(token, metadata_nvr) {
    def response = [:]
    try {
        retry(60) {  // retry failing pkg for 60m
            response = [:]  // ensure we aren't left looking at a previous response when pushToOMPS fails
            response = pushToOMPS(token, metadata_nvr)
            if (response.status != 200) {
                sleep(60)
                error "${[metadata_nvr: metadata_nvr, response_content: response.content]}"
            }
        }
    } catch (err) {
        if (response.status != 200) {
            return [
                metadata_nvr: metadata_nvr,
                response_status: response.status,
                response_content: response.content
            ]
        } else {
            // failed because of something other than bad request; note that instead
            return err
        }
    }
    return null
}

// Push to OMPS the latest dev metadata builds against a list of operator builds.
def stagePushDevMetadata(operatorBuilds) {
    def token = retrieveBotToken()
    def metadata_nvrs = getMetadataNVRs(operatorBuilds.collect { it.nvr }, "dev")
    def errors = [:]
    parallel metadata_nvrs.collectEntries { nvr -> [
        (nvr.replaceAll("-operator-metadata-container.*", "")): { ->
            err = pushToOMPSWithRetries(token, nvr)
            if (err) {
                errors[nvr] = err
            } else {
                currentBuild.description += "\n  ${nvr}"
            }
        }
    ]}
   
    if (errors) {
        error "${errors}"
    }
}

// Attach to the metadata advisory the latest stage/prod metadata builds against a list of operator builds.
def stageAttachMetadata(operatorBuilds) {
    def metadata_nvrs = getMetadataNVRs(operatorBuilds.collect { it.nvr }, params.STREAM)

    elliott """
        change-state -s NEW_FILES
        -a ${params.METADATA_ADVISORY}
        ${params.DRY_RUN ? "--noop" : ""}
    """

    attachToAdvisory(params.METADATA_ADVISORY, metadata_nvrs)

    /*
    // this would be convenient, except that we don't have a way
    // to set the CDN repos first, and can't move to QE without that.
    elliott """
        change-state -s QE
        -a ${params.METADATA_ADVISORY}
        ${params.DRY_RUN ? "--noop" : ""}
    """
    */
}

return this

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

@NonCPS
def parseAndFilterOperators(lines) {
    def data = []
    lines.split().each { line ->
        // label, name, nvr, version, component
        def fields = line.split(',')
        if (fields[0]) {
            data.add([
                name: fields[1],
                nvr: fields[2],
                version: fields[3].replace("v", ""),
                component: fields[4],
            ])
        }
    }
    return data
}

def retrieveBotToken() {
    def token = ""
    withCredentials([usernamePassword(credentialsId: 'quay_appregistry_omps_bot', usernameVariable: 'QUAY_USERNAME', passwordVariable: 'QUAY_PASSWORD')]) {
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

def getImagesData(include) {
    if (include) {
        include = "--images " + commonlib.cleanCommaList(include)
    }
    doozer """
        ${include}
        images:print
        --label 'com.redhat.delivery.appregistry'
        --short '{label},{name},{build},{version},{component}'
    """
}

def fetchNVRsFromAdvisories(advisories) {
    commonlib.cleanCommaList(advisories).split(",").collect { advisory ->
        readJSON(text: elliott("get --json - ${advisory}")).errata_builds.values().flatten()
    }.flatten()
}

def findImageNVRsInAdvisories(images, advisoriesNVRs) {
    images.collect {
        image -> [
            name: image.name,
            nvr: advisoriesNVRs.find { it.startsWith(image.component) }
        ]
    }
}

def pushToOMPS(token, metadata_nvr) {
    httpRequest(
        url: "https://omps-prod.cloud.paas.psi.redhat.com/v2/redhat-operators-art/koji/${metadata_nvr}",
        httpMode: 'POST',
        customHeaders: [[name: 'Authorization', value: token]],
        timeout: 60,
        validResponseCodes: "200:599",
    )
}

def getMetadataNVRs(operatorNVRs, stream) {
    def nvrFlags = operatorNVRs.collect { "--nvr ${it}" }.join(" ")
    doozer("operator-metadata:latest-build --stream ${stream} ${nvrFlags}")
}

def attachToAdvisory(advisory, metadata_nvrs) {
    def elliott_build_flags = []
    metadata_nvrs.split().each { nvr -> elliott_build_flags.add("--build ${nvr}") }

    elliott """
        find-builds -k image
        ${elliott_build_flags.join(" ")}
        --attach ${advisory}
    """
}

def stageFetchOperatorImages() {
    operatorData = parseAndFilterOperators(getImagesData(params.IMAGES.trim()))

    if (params.STREAM in ["stage", "prod"]) {
        def advisoriesNVRs = fetchNVRsFromAdvisories(params.OLM_OPERATOR_ADVISORIES)
        operatorData = findImageNVRsInAdvisories(operatorData, advisoriesNVRs)

        if (operatorData.any { it.nvr == null }) {
            currentBuild.description += """\n
            Advisories missing operators ${operatorData.findAll { it.nvr }.collect { it.name }.join(",")}
            """
            echo """
            ERROR: The following operators were not found in provided advisories.
            ${operatorData.findAll { !it.nvr }.collect { it.name }.join(",")}

            Possible solutions:
            1. Add more advisories in OLM_OPERATOR_ADVISORIES parameter, that have the missing operators attached
            2. Attach missing operators to at least one of the provided advisories: ${params.OLM_OPERATOR_ADVISORIES}
            3. Limit the expected operators in IMAGES parameter: ${operatorData.findAll { it.nvr }.collect { it.name }.join(",")}
            """
            error "operators not found"
        }
    }
    return operatorData
}

def stageBuildMetadata(operatorData) {
    def nvrs = operatorData.collect { item -> item.nvr }

    doozer """
        operator-metadata:build ${nvrs.join(' ')}
        ${params.FORCE_METADATA_BUILD ? "-f" : ""}
        --stream ${params.STREAM}
    """
}

def stagePushDevMetadata(operatorData) {
    def errors = []
    def token = retrieveBotToken()
    for (def i = 0; i < operatorData.size(); i++) {
        def build = operatorData[i]
        def metadata_nvr = getMetadataNVRs([build.nvr], params.STREAM)

        def response = [:]
        try {
            retry(errors ? 3 : 60) { // retry the first failing pkg for 30m; after that, give up after 1m30s
                response = [:] // ensure we aren't looking at a previous response
                response = pushToOMPS(token, metadata_nvr)
                if (response.status != 200) {
                    sleep(30)
                    error "${[metadata_nvr: metadata_nvr, response_content: response.content]}"
                }
            }
        } catch (err) {
            if (response.status != 200) {
                errors.add([
                    metadata_nvr: metadata_nvr,
                    response_status: response.status,
                    response_content: response.content
                ])
            } else {
                // failed because of something other than bad request; note that instead
                errors.add(err)
            }
            continue // without claiming any success
        }
        currentBuild.description += "\n  ${metadata_nvr}"
    }
    if (!errors.isEmpty()) {
        error "${errors}"
    }
}

def stageAttachMetadata(operatorData) {
    def metadata_nvrs = getMetadataNVRs(operatorData.collect { it.nvr }, params.STREAM)

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

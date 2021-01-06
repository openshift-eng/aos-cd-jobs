import java.util.concurrent.ConcurrentHashMap

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
        --show-non-release
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
    Have doozer find the latest metadata container build NVRs from given operator container NVRs.
    param operatorNVRs: list of operator container NVRs
    param stream: dev|stage|prod depending on which we are looking for
    returns: a list of metadata container NVRs
*/
def getMetadataNVRs(operatorNVRs, stream) {
    def nvrFlags = operatorNVRs.collect { "--nvr ${it}" }.join(" ")
    return doozer("operator-metadata:latest-build --stream ${stream} ${nvrFlags}").split()
}

def removeDifferentStreamBuilds(advisory) {
    def attachedBuilds = fetchNVRsFromAdvisories(advisory)
    def differentStreamBuilds = attachedBuilds.findAll {
        it -> it.indexOf(".${params.STREAM}") == -1
    }
    def elliottCmdBuildFlags = []
    differentStreamBuilds.each {
        it -> elliottCmdBuildFlags.add("--build ${it}")
    }
    if (elliottCmdBuildFlags) {
        elliott """
            find-builds --kind image
            ${elliottCmdBuildFlags.join(" ")}
            -a ${advisory}
            --remove
        """
    }
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
    wrap pushToOMPS with retries:
    retry until the CVP for the container build completes
    retry 2 failures
    timeout after an hour regardless
*/
def pushToOMPSWithRetries(token, metadata_nvr) {
    timeout (time: 2, unit: "HOURS") {
        def err = null
        def cvpTries = 0
        def failures = 0
        while (true) {
            response = [:]
            try {
                response = pushToOMPS(token, metadata_nvr)
                if (response.status == 200) {
                    break  // success!
                }
                if (response.status == 400 && response.content.contains("required test results missing")) {
                    // this is the error we get when the CVP hasn't run yet; retry until tests complete
                    echo "waiting for CVP tests to complete (${cvpTries++})"
                    sleep(60)
                    continue
                }
                // something else went wrong - could be transient, record the error we end up with
                error([
                    metadata_nvr: metadata_nvr,
                    response_status: response.status,
                    response_content: response.content,
                ].toString())
            } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
                // This probably means we got a timeout or user abort *during* the request. We don't want to retry.
                err = e
                throw err
            } catch (e) {
                // could also fail because of some error other than bad response
                err = e
            }

            if (failures++ > 2) {
                throw err
            }
            sleep(60)
        }
    }
}

// Push to OMPS the latest dev metadata builds against a list of operator builds.
def stagePushDevMetadata(operatorBuilds) {
    def token = retrieveBotToken()
    def metadata_nvrs = getMetadataNVRs(operatorBuilds.collect { it.nvr }, "dev")
    def errors = new ConcurrentHashMap()
    def distgits = operatorBuilds.collect { it.distgit }
    def owners = buildlib.get_owners("--working-dir ${workDir} -g openshift-${buildVersion}", distgits)

    def nvrDistgits = [metadata_nvrs, distgits].transpose()  // list of [metadata_nvr, distgit_repo] pairs
    def stepsForParallel = nvrDistgits.collectEntries { entry ->
        def (nvr, distgit) = entry
        def operator_name = nvr.replaceAll("-operator-metadata-container.*", "")
        def step = {
            try {
                pushToOMPSWithRetries(token, nvr)
                currentBuild.description += "\n  ${nvr}"
            } catch(org.jenkinsci.plugins.workflow.steps.FlowInterruptedException err) {
                // we got a timeout or user abort *during* the request, don't need to disturb image owner, that's not something the image owner needs to hear about.
                errors[nvr] = err
            } catch(err) {
                errors[nvr] = err
                image_owners = owners["images"][distgit]
                if (image_owners) {
                    body = """
What do I need to do?
---------------------
An error occurred during importing your operator's metadata to OMPS. Until this issue is addressed,
your upstream changes may not be reflected in the product build.

Please review the error message reported below to see if the issue is due to upstream
content. If it is not, the Automated Release Tooling (ART) team will engage to address
the issue. Please direct any questions to the ART team (#aos-art on slack).

Error Reported
--------------
Brew NVR: ${nvr}
Error message: ${err}
CVP test result: http://external-ci-coldstorage.datahub.redhat.com/cvp/cvp-redhat-operator-metadata-validation-test/${nvr}/
(test results will be in a random hash dir under the link)

Why am I receiving this?
------------------------
You are receiving this message because you are listed as an owner for an
OpenShift related image.
"""
                    commonlib.email(
                        to: image_owners.join(","),
                        from: "aos-art-automation@redhat.com",
                        replyTo: "aos-team-art@redhat.com",
                        subject: "[ACTION REQUIRED] Failed to import operator metadata ${nvr} to OMPS",
                        body: body + "\n------\nConsole output: ${commonlib.buildURL('console')}\n${currentBuild.description}",
                    )
                }
            }
        }
        [operator_name, step]
    }

    parallel stepsForParallel

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

    removeDifferentStreamBuilds(params.METADATA_ADVISORY)
    attachToAdvisory(params.METADATA_ADVISORY, metadata_nvrs)

    try {
        elliott """
            change-state -s QE
            -a ${params.METADATA_ADVISORY}
            ${params.DRY_RUN ? "--noop" : ""}
        """
    } catch(e) {
        // the first time we do this for an advisory, we don't have a way to set the CDN repos first, so move to QE will fail.
        echo "failed to move metadata advisory to QE state; check CDN repos and script output"
        currentBuild.description += "\nFailed to move metadata advisory to QE state; check CDN repos and script output"
    }
}

return this

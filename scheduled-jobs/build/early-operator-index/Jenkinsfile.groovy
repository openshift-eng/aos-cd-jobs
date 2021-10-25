properties([
    buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '100')),
    disableConcurrentBuilds(),
    disableResume(),
])

node {

    /*
     * Builds an index image with the latest build of operator bundles. This is used by the
     * multi-arch team (contact Jeremy Poulin) to validate operators in multi-arch envrionments
     * prior to their availability in the staging index.
     */
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    workDir = "${env.WORKSPACE}/doozer_working"
    sh "rm -rf ${workDir}"
    ocpVer = "4.10"
    operatorIndexBaseVersion = "4.9"
    operatorRegistryVersion = "4.9"
    
    // Print out bundle pullspecs alongside of distgit keys to help identify bundles which have not been built yet.
    echo "Doozer pullspecs by distgit_key"
    buildlib.doozer("--group=openshift-${ocpVer} --working-dir=${workDir} olm-bundle:print " + '\'{distgit_key} {bundle_pullspec}\'')
    
    // Note this logic will start to fail when versions of the operators start to be attached to
    // advisories and pushed to staging.
    def pullspecs = buildlib.doozer("--group=openshift-${ocpVer} --working-dir=${workDir} olm-bundle:print " + '{bundle_pullspec}',
            [capture: true]).trim().split()
    
    request = [
        'bundles': pullspecs.findAll { it != "None" },  // Ignore bundle if it has not been built yet
        'from_index': "registry-proxy.engineering.redhat.com/rh-osbs/iib-pub-pending:v${operatorIndexBaseVersion}",
        'binary_image': "registry-proxy.engineering.redhat.com/rh-osbs/openshift-ose-operator-registry:v${operatorRegistryVersion}.0"
    ]

    writeJSON(file: 'request.json', json: request, pretty: 4)

    echo 'Content of the request:'
    sh 'cat request.json'

    resp_string = commonlib.shell(
        returnStdout: true,
        script:'curl -u : --negotiate -X POST -H "Content-Type: application/json" https://iib.engineering.redhat.com/api/v1/builds/add -d @request.json'
    )

    echo "Received response:\n${resp_string}"

    resp = readJSON(text: resp_string)
    
    if (resp.containsKey('error')) {
        error("IIB reported error")
    }
    
    job_id = resp['id']

    success = false
    for(int i = 0; i < 20; i++) { // IIB will take time to run
        sleep 60  // give IIB some time, then check in by trying to mirror
        try {
            commonlib.shell("oc image mirror  --keep-manifest-list --filter-by-os='.*' registry-proxy.engineering.redhat.com/rh-osbs/iib:${job_id} quay.io/openshift-release-dev/ocp-release-nightly:iib-int-index-art-operators-${ocpVer}")
            echo "Successfully mirrored image!"
            success = true
            break
        } catch (e) {
            echo "Exception! ${e}"
        }
    }

    if (!success) {
        error("Failures reported and retries exhausted")
    }
}

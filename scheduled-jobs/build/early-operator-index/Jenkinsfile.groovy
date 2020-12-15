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

    // Note this logic will start to fail when versions of the operators start to be attached to
    // advisories and pushed to staging.
    def pullspecs = buildlib.doozer("-x cluster-nfd-operator --group=openshift-4.7 --working-dir=${workDir} olm-bundle:print " + '{bundle_pullspec}',
            [capture: true]).trim().split()

    // At the time of this writing cluster-nfd-operator builds cannot be added to the staging index
    // because all builds of it are 1.0.0 and we cannot replace an existing version.
    pullspecs = pullspecs.findAll { !it.contains('nfd') }
    
    request = [
        'bundles': pullspecs,
        'from_index': 'registry-proxy.engineering.redhat.com/rh-osbs/iib-pub-pending:v4.7'
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
    job_id = resp['id']

    for(int i = 0; i < 20; i++) { // IIB will take time to run
        sleep 60  // give IIB some time, then check in by trying to mirror
        try {
            commonlib.shell("oc image mirror  --keep-manifest-list --filter-by-os='.*' registry-proxy.engineering.redhat.com/rh-osbs/iib:${job_id} quay.io/openshift-release-dev/ocp-release-nightly:iib-int-index-art-operators-4.7")
            echo "Successfully mirrored image!"
            break
        } catch (e) {
            echo "Exception! ${e}"
        }
    }

}

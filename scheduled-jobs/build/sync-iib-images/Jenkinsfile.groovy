properties([disableConcurrentBuilds()])

node {

    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    for(int i = 0; i < 10000; i++) { // don't run forever so that logs is not infinite
        try {
            def messageContent = waitForCIMessage checks: [], overrides: [topic: 'Consumer.rh-jenkins-ci-plugin.397637dc-0cc8-4c35-bde8-b841024dc6d1.VirtualTopic.eng.ci.redhat-container-image.index.built'], providerName: 'Red Hat UMB', selector: ''
            echo "${messageContent}"
            msgObj = readJSON text: messageContent
            // Example: https://datagrepper.engineering.redhat.com/id?id=ID:jenkins-1-qnt2m-32829-1599730867657-210799:1:1:1:1&is_raw=true&size=extra-large
            name = msgObj['artifact']['name']
            idx_image = msgObj['index']['index_image']
            ocp_ver = msgObj['index']['ocp_version']
            echo "name: ${name}"
            echo "idx_image: ${idx_image}"
            echo "ocp_ver: ${ocp_ver}"
            if (name.startsWith('ocp-release-nightly-metadata-container') || name.startsWith('cluster-nfd-operator-bundle-container')) {
                dest_name = "quay.io/openshift-release-dev/ocp-release-nightly:iib-stage-cluster-nfd-operator-${ocp_ver}"
                sh "oc image mirror ${idx_image} ${dest_name}"
            }
            break
        } catch (e) {
            echo "Exception! ${e}"
            if ("${e}".toLowerCase().contains('timeout')) {
                echo "Timeout, but retrying..."
            } else {
                throw e
            }
        }
    }

}

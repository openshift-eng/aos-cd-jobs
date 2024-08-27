properties([
    buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '100')),
    disableConcurrentBuilds(),
    disableResume(),
])

node {

    /* Awaits messages from the operator pipeline describing an new index built for the ptp operator.
     * When it is received, the index index image (which is the latest ptp-operator bundle + the staging index image)
     * will be mirror out to quay for consumption by the multi-arch team
     */
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    for(int i = 0; i < 1000; i++) { // don't run forever so that logs is not infinite
        try {
            echo "Wait for incoming message"
            def messageContent = waitForCIMessage checks: [], overrides: [topic: 'Consumer.openshift-art-bot.397637dc-0cc8-4c35-bde8-b841024dc6d1.VirtualTopic.eng.ci.redhat-container-image.index.built'], providerName: 'Red Hat UMB', selector: ''
            msgObj = readJSON text: messageContent
            // https://datagrepper.engineering.redhat.com/raw?topic=/topic/VirtualTopic.eng.ci.redhat-container-image.index.built
            // Example: https://datagrepper.engineering.redhat.com/id?id=ID:jenkins-1-jmddf-43869-1720197152936-81065:1:1:1:1&is_raw=true&size=extra-large
            name = msgObj['artifact']['nvr']
            idx_image = msgObj['index']['index_image']
            ocp_ver = msgObj['index']['ocp_version'] // "v4.16"

            if (name.startsWith('ose-ptp-operator-metadata') || name.startsWith('ose-ptp-operator-bundle')) {
                echo "Processing {name: ${name}, idx_image: ${idx_image}, ocp_ver: ${ocp_ver}"
                buildlib.registry_quay_dev_login()
                dest_name = "quay.io/openshift-release-dev/ocp-release-nightly:iib-int-index-cluster-ose-ptp-operator-${ocp_ver}"
                buildlib.withAppCiAsArtPublish() {
                    sh "oc registry login"
                    sh "oc image mirror ${idx_image} ${dest_name}"
                }
            }
            else {
                echo "Ignoring {name: ${name}, idx_image: ${idx_image}, ocp_ver: ${ocp_ver}"
            }
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

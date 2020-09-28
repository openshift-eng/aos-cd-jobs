properties([buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '100')),
            disableConcurrentBuilds()])

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
            def messageContent = waitForCIMessage checks: [], overrides: [topic: 'Consumer.rh-jenkins-ci-plugin.397637dc-0cc8-4c35-bde8-b841024dc6d1.VirtualTopic.eng.ci.redhat-container-image.index.built'], providerName: 'Red Hat UMB', selector: ''
            echo "${messageContent}"
            msgObj = readJSON text: messageContent
            // Example: https://datagrepper.engineering.redhat.com/id?id=ID:jenkins-1-qnt2m-32829-1599730867657-210799:1:1:1:1&is_raw=true&size=extra-large
            name = msgObj['artifact']['nvr']
            idx_image = msgObj['index']['index_image']
            ocp_ver = msgObj['index']['ocp_version']
            echo "name: ${name}"
            echo "idx_image: ${idx_image}"
            echo "ocp_ver: ${ocp_ver}"
            if (name.startsWith('ose-ptp-operator-metadata') || name.startsWith('ose-ptp-operator-bundle')) {
                dest_name = "quay.io/openshift-release-dev/ocp-release-nightly:iib-int-index-cluster-ose-ptp-operator-${ocp_ver}"
                sh "KUBECONFIG=/home/jenkins/kubeconfigs/art-publish.kubeconfig oc registry login"
                sh "oc image mirror ${idx_image} ${dest_name}"
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

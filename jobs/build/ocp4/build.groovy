#!/usr/bin/env groovy


def messageSuccess(mirrorURL) {
    try {
        timeout(3) {
            sendCIMessage(
                messageContent: "New build for OpenShift: ${version.stream}",
                messageProperties:
                    """build_mode=pre-release
                    puddle_url=${rpmMirror.url}/${rpmMirror.plashetDirName}
                    image_registry_root=registry.reg-aws.openshift.com:443
                    product=OpenShift Container Platform
                    """,
                messageType: 'ProductBuildDone',
                overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
                providerName: 'Red Hat UMB'
            )
        }
    } catch (mex) {
        echo "Error while sending CI message: ${mex.getMessage()}"
    }
}

return this

#!/usr/bin/env groovy

node {
    try {
        checkout scm
        commonlib = load("pipeline-scripts/commonlib.groovy")
        slacklib = commonlib.slacklib
        sh "./scripts/github-ldap-mapping-update.sh"
    } catch (e) {
        notifyFailed()
        throw e
    }
    
}

def notifyFailed() {
    slackChannel = slacklib.to('#ops-testplatform')
    slackChannel.failure("Unable to sync LDAP content to the configMap github-ldap-mapping on app.ci; Contact ART team to inspect this job run")
}

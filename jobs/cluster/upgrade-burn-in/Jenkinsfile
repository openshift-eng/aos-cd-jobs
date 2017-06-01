#!/usr/bin/env groovy

node('buildvm-devops') {
    
    stage( 'Burn-in operation' ) {
        sshagent(['cicd_cluster_key']) {
            // Agent forwarding is enabled in order to allow openshift-ansible to 
            // access all nodes on the cluster.
            sh "ssh -A -o StrictHostKeyChecking=no root@master1.cicd.openshift.com echo hello"
        }
    }

}

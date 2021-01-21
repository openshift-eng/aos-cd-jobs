#!/usr/bin/env groovy
node {
    checkout scm
    load("pipeline-scripts/commonlib.groovy").describeJob("odo_sync", """
        ----------------------------------
        Sync OpenShift Do client to mirror
        ----------------------------------
        http://mirror.openshift.com/pub/openshift-v4/clients/odo/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "VERSION",
            description: "Desired version name. Example: v1.0.3",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "SOURCES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/odo/1.2.5-1/signed/all/",
            defaultValue: "",
            trim: true,
        )
    }

    stages {
        stage("Validate params") {
            steps {
                script {
                    if (!params.VERSION) {
                        error "VERSION must be specified"
                    }
                }
            }
        }
        stage("Clean working dir") {
            steps {
                sh "rm -rf ${params.VERSION}"
            }
        }
        stage("Download binaries") {
            steps {
                script {
                    downloadRecursive(params.SOURCES_LOCATION, params.VERSION)
                }
            }
        }
        stage("Sync to mirror") {
            steps {
                sh "tree ${params.VERSION}"
                sshagent(['aos-cd-test']) {
                    sh "scp -r ${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/odo/"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/clients/odo/latest"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/clients/odo -v"
                }
            }
        }
    }
}

def downloadRecursive(path, destination) {
    sh "wget --recursive --no-parent --reject 'index.html*' --no-directories --directory-prefix ${destination} ${path}"
}

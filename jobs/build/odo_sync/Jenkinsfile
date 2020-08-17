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
            defaultValue: ""
        )
        string(
            name: "LINUX_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/odo/1.2.5-1/signed/linux/",
            defaultValue: ""
        )
        string(
            name: "MACOS_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/odo/1.2.5-1/signed/macos/",
            defaultValue: ""
        )
        string(
            name: "WINDOWS_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/odo/1.2.5-1/signed/windows/",
            defaultValue: ""
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
            parallel {
                stage("linux")   { steps { script { downloadRecursive(params.LINUX_BINARIES_LOCATION,   params.VERSION) }}}
                stage("macos")   { steps { script { downloadRecursive(params.MACOS_BINARIES_LOCATION,   params.VERSION) }}}
                stage("windows") { steps { script { downloadRecursive(params.WINDOWS_BINARIES_LOCATION, params.VERSION) }}}
            }
        }
        stage("Combine SHA256SUMs") {
            steps {
                sh "cat ${params.VERSION}/SHA256SUM.* >> ${params.VERSION}/SHA256SUM"
                sh "rm ${params.VERSION}/SHA256SUM.*"
                sh "mv ${params.VERSION}/SHA256SUM ${params.VERSION}/sha256sum.txt"
            }
        }

        stage("Sync to mirror") {
            steps {
                sh "tree ${params.VERSION}"
                sh "cat ${params.VERSION}/sha256sum.txt"

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

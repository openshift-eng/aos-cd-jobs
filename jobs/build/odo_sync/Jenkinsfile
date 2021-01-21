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
            name: "LINUX_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/odo/1.2.5-1/signed/linux/",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "MACOS_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/odo/1.2.5-1/signed/macos/",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "WINDOWS_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/odo/1.2.5-1/signed/windows/",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "SITE_TARBALL_LOCATION",
            description: "(Optional) Example: https://github.com/openshift/odo/releases/download/v2.0.1/site.tar.gz",
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
            parallel {
                stage("linux")   { steps { script { downloadRecursive(params.LINUX_BINARIES_LOCATION,   params.VERSION) }}}
                stage("macos")   { steps { script { downloadRecursive(params.MACOS_BINARIES_LOCATION,   params.VERSION) }}}
                stage("windows") { steps { script { downloadRecursive(params.WINDOWS_BINARIES_LOCATION, params.VERSION) }}}
            }
        }
        stage("Download site") {
            when  { expression { ! params.SITE_TARBALL_LOCATION.isEmpty() }}
            steps { script { downloadRecursive(params.SITE_TARBALL_LOCATION, params.VERSION) }}
        }
        stage("Combine sha256sums") {
            steps {
                sh "cat ${params.VERSION}/sha256sum.* >> ${params.VERSION}/SHA256SUM"
                sh "rm ${params.VERSION}/sha256sum.*"
                sh "mv ${params.VERSION}/SHA256SUM ${params.VERSION}/sha256sum.txt"
                script {
                    if (!params.SITE_TARBALL_LOCATION.isEmpty()) {
                        sh "sha256sum ${params.VERSION}/site.tar.gz >> ${params.VERSION}/sha256sum.txt"
                    }
                }
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

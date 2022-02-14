#!/usr/bin/env groovy
node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.describeJob("rosa_sync", """
        ------------------------------------------------------
        Sync ROSA (Red Hat OpenShift Service on AWS) to mirror
        ------------------------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/rosa_sync/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "VERSION",
            description: "Desired version name. Example: 1.6.0",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "SOURCES_LOCATION",
            description: "Example: https://download.eng.bos.redhat.com/staging-cds/developer/rosa/1.0.5-1856674/signed/all/",
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
                script {
                    commonlib.syncDirToS3Mirror("${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/rosa/${params.VERSION}/")
                    commonlib.syncDirToS3Mirror("${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/rosa/latest/")
                }
            }
        }
    }
}

def downloadRecursive(path, destination) {
    sh "wget --recursive --no-parent --reject 'index.html*' --no-directories --directory-prefix ${destination} ${path}"
}

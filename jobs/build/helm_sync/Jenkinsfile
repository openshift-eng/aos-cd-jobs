#!/usr/bin/env groovy
node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.describeJob("helm_sync", """
        --------------------------
        Sync Helm client to mirror
        --------------------------
        http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/helm/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "VERSION",
            description: "Desired version name on mirror. Example: 3.0.5",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "SOURCES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/helm/3.5.0-6/signed/all/",
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
                    if (!params.SOURCES_LOCATION) {
                        error "SOURCES_LOCATION must be specified"
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
                    commonlib.syncDirToS3Mirror("${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/helm/${params.VERSION}/")
                    commonlib.syncDirToS3Mirror("${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/helm/latest/")
                }
            }
        }
    }
}

def downloadRecursive(path, destination) {
    sh "wget --recursive --no-parent --reject 'index.html*' --no-directories --directory-prefix ${destination} ${path}"
}

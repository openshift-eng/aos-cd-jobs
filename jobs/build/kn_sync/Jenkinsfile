#!/usr/bin/env groovy
node {
    checkout scm
    load("pipeline-scripts/commonlib.groovy").describeJob("kn_sync", """
        ----------------------------------------------
        Sync the knative (serverless) client to mirror
        ----------------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/serverless/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "VERSION",
            description: "Desired version name. Example: 0.20.0",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "SOURCES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/openshift-serverless-clients/0.20.0-6/signed/all/",
            defaultValue: "",
            trim: true,
        )
        booleanParam(
            name: 'SKIP_ARM64',
            description: 'Skip mirroring arm64 binary.',
            defaultValue: false,
        )
    }

    stages {
        stage("Validate params") {
            steps {
                script {
                    if (!params.VERSION) {
                        error "VERSION must be specified"
                    }
                    if (params.SOURCES_LOCATION[-1] != "/") {
                        error "Location should end with a trailing slash (to not confuse wget)"
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
                    downloadRecursive(params.SOURCES_LOCATION, params.VERSION, params.SKIP_ARM64)
                }
            }
        }
        stage("Sync to mirror") {
            steps {
                sh "tree ${params.VERSION}"
                script {
                    commonlib.syncDirToS3Mirror("${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/serverless/${params.VERSION}/")
                    commonlib.syncDirToS3Mirror("${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/serverless/latest/")
                }
                sshagent(['aos-cd-test']) {
                    sh "scp -r ${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/x86_64/clients/serverless/"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/x86_64/clients/serverless/latest"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/x86_64/clients/serverless -v"
                }
            }
        }
    }
}

def downloadRecursive(path, destination, skip_arm64) {
    skip_param = ""
    if (skip_arm64) {
        skip_param = ",*arm64.tar.gz"
    }
    sh "wget --recursive --no-parent --reject 'index.html*${skip_param}' --no-directories --directory-prefix ${destination} ${path}"
}  

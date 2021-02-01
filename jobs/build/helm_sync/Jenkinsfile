#!/usr/bin/env groovy
node {
    checkout scm
    load('pipeline-scripts/commonlib.groovy').describeJob("helm_sync", """
        --------------------------
        Sync Helm client to mirror
        --------------------------
        http://mirror.openshift.com/pub/openshift-v4/clients/helm/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "VERSION",
            description: "Desired version name on mirror. Example: 3.0.1",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "FROM_VERSION",
            description: "The build version to get the artifacts from. e.g. 3.5.0-6 from: http://download.eng.bos.redhat.com/staging-cds/developer/helm/3.5.0-6/signed/",
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
                    if (!params.FROM_VERSION) {
                        error "FROM_VERSION must be specified"
                    }
                }
            }
        }
        stage("Clean working dir") {
            steps {
                sh "rm -rf ${params.VERSION} && mkdir ${params.VERSION}"
            }
        }
        stage("Copy binaries") {
            steps {
                sh """
                cp /mnt/redhat/staging-cds/developer/helm/${params.FROM_VERSION}/signed/*/helm* ${params.VERSION}
                cd ${params.VERSION}
                sha256sum * > sha256sum.txt
                """
            }
        }
        stage("Sync to mirror") {
            steps {
                sh "tree ${params.VERSION}"
                sh "cat ${params.VERSION}/sha256sum.txt"

                sshagent(['aos-cd-test']) {
                    sh "scp -r ${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/helm/"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/clients/helm/latest"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/clients/helm -v"
                }
            }
        }
    }
}

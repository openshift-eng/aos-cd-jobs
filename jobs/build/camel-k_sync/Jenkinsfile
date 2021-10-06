#!/usr/bin/env groovy
node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.describeJob("camel-k_sync", """
        -----------------------------
        Sync Camel-K client to mirror
        -----------------------------
        http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/camel-k/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "VERSION",
            description: "Desired version name. Example: 1.0",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "LINUX_BINARIES_LOCATION",
            description: "Example: http://rcm-guest.app.eng.bos.redhat.com/rcm-guest/staging/integration/RHI-1.0.0.TP1-CR7/linux-client-1.0.0.fuse-jdk11-800042-redhat-00006.tar.gz",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "MACOS_BINARIES_LOCATION",
            description: "Example: http://rcm-guest.app.eng.bos.redhat.com/rcm-guest/staging/integration/RHI-1.0.0.TP1-CR7/mac-client-1.0.0.fuse-jdk11-800042-redhat-00006.tar.gz",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "WINDOWS_BINARIES_LOCATION",
            description: "Example: http://rcm-guest.app.eng.bos.redhat.com/rcm-guest/staging/integration/RHI-1.0.0.TP1-CR7/windows-client-1.0.0.fuse-jdk11-800042-redhat-00006.tar.gz",
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
                sh "mkdir ${params.VERSION}"
            }
        }
        stage("Download artifacts") {
            parallel {
                stage("linux")   { steps { sh "curl -sLf ${params.LINUX_BINARIES_LOCATION} -o ${params.VERSION}/camel-k-client-${params.VERSION}-linux-64bit.tar.gz" }}
                stage("macos")   { steps { sh "curl -sLf ${params.MACOS_BINARIES_LOCATION} -o ${params.VERSION}/camel-k-client-${params.VERSION}-mac-64bit.tar.gz" }}
                stage("windows") { steps { sh "curl -sLf ${params.WINDOWS_BINARIES_LOCATION} -o ${params.VERSION}/camel-k-client-${params.VERSION}-windows-64bit.tar.gz" }}
            }
        }
        stage("Generate MD5 sum") {
            steps {
                sh """
                cd ${params.VERSION} &&
                md5sum camel-k-client-${params.VERSION}-linux-64bit.tar.gz   > camel-k-client-${params.VERSION}-linux-64bit.tar.gz.md5 &&
                md5sum camel-k-client-${params.VERSION}-mac-64bit.tar.gz     > camel-k-client-${params.VERSION}-mac-64bit.tar.gz.md5 &&
                md5sum camel-k-client-${params.VERSION}-windows-64bit.tar.gz > camel-k-client-${params.VERSION}-windows-64bit.tar.gz.md5 &&
                cd ..
                """
                sh "tree ${params.VERSION}"
                sh "cat ${params.VERSION}/*.md5"
            }
        }
        stage("Sync to mirror") {
            steps {
                script {
                    commonlib.syncDirToS3Mirror("./${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/camel-k/${params.VERSION}/")
                    commonlib.syncDirToS3Mirror("./${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/camel-k/latest/")
                }

                sshagent(['aos-cd-test']) {
                    sh "scp -r ${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/x86_64/clients/camel-k/"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/x86_64/clients/camel-k/latest"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/x86_64/clients/camel-k -v"
                }
            }
        }
    }
}

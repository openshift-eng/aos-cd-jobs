#!/usr/bin/env groovy
node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.describeJob("camel-k_sync", """
        -----------------------------
        Sync Camel-K client to mirror
        -----------------------------
        https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/camel-k/

        Timing: This is only ever run by humans, upon request.
    """)

    properties([
        disableResume(),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                string(
                    name: "VERSION",
                    description: "Desired version name. Example: 1.0",
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: "LINUX_BINARIES_LOCATION",
                    description: "Example: https://download.eng.bos.redhat.com/devel/candidates/middleware/integration/RHI-1.0.0.TP1-CR7/linux-client-1.0.0.fuse-jdk11-800042-redhat-00006.tar.gz",
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: "MACOS_BINARIES_LOCATION",
                    description: "Example: https://download.eng.bos.redhat.com/devel/candidates/middleware/integration/RHI-1.0.0.TP1-CR7/mac-client-1.0.0.fuse-jdk11-800042-redhat-00006.tar.gz",
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: "WINDOWS_BINARIES_LOCATION",
                    description: "Example: https://download.eng.bos.redhat.com/devel/candidates/middleware/integration/RHI-1.0.0.TP1-CR7/windows-client-1.0.0.fuse-jdk11-800042-redhat-00006.tar.gz",
                    defaultValue: "",
                    trim: true,
                )
            ]
        ]
    ])

    stage("Validate params") {
        if (!params.VERSION) {
            error "VERSION must be specified"
        }
    }

    stage("Clean working dir") {
        sh "rm -rf ${params.VERSION}"
        sh "mkdir ${params.VERSION}"
    }

    stage("Download artifacts") {
        parallel (
            "linux":   { sh "curl -sLf ${params.LINUX_BINARIES_LOCATION} -o ${params.VERSION}/camel-k-client-${params.VERSION}-linux-64bit.tar.gz" },
            "macos":   { sh "curl -sLf ${params.MACOS_BINARIES_LOCATION} -o ${params.VERSION}/camel-k-client-${params.VERSION}-mac-64bit.tar.gz" },
            "windows": { sh "curl -sLf ${params.WINDOWS_BINARIES_LOCATION} -o ${params.VERSION}/camel-k-client-${params.VERSION}-windows-64bit.tar.gz" }
        )
    }

    stage("Generate MD5 sum") {
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

    stage("Sync to mirror") {
        commonlib.syncDirToS3Mirror("./${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/camel-k/${params.VERSION}/")
        commonlib.syncDirToS3Mirror("./${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/camel-k/latest/")
    }
}

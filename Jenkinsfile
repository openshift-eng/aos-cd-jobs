#!/usr/bin/env groovy
node {
    checkout scm
    def release = load("pipeline-scripts/release.groovy")
    def buildlib = release.buildlib
    def commonlib = buildlib.commonlib

    commonlib.describeJob("coreos-installer_sync", """
        <h2>Sync contents of the coreos-installer RPM to mirror</h2>
        https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/coreos-installer/

        Timing: This is only ever run by humans, upon request.
    """)

    properties([
        disableResume(),
        buildDiscarder(
            logRotator(
                artifactDaysToKeepStr: '',
                artifactNumToKeepStr: '',
                daysToKeepStr: '',
                numToKeepStr: ''
            )
        ),
        [
            $class: 'ParametersDefinitionProperty',
            parameterDefinitions: [
                string(
                    name: "NVR",
                    description: "NVR of the blessed brew build",
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: "VERSION",
                    description: "Desired version name. Example: v3.0.1",
                    defaultValue: "",
                    trim: true,
                ),
                string(
                    name: "ARCHES",
                    description: "Arches to extract from the brew build. Defaults to all contained in the rpm",
                    defaultValue: "",
                    trim: true,
                ),
                commonlib.dryrunParam(),
                commonlib.mockParam(),
            ],
        ]
    ])

    workdir = "${env.WORKSPACE}/coreos-installer_sync"
    commonlib.checkMock()
    buildlib.cleanWorkdir(workdir)

    stage("Validate params") {
        if (!params.NVR) {
            error "NVR must be specified"
        }
        if (!params.VERSION) {
            error "VERSION must be specified"
        }
        currentBuild.displayName = "${params.VERSION}"
    }

    stage("Download RPM") {
        commonlib.shell(
            script: """
                set -exuo pipefail
                cd ${workdir}
                rm --recursive --force ./*
                brew --quiet download-build ${params.NVR}
                shopt -s nullglob
                rm --force *bootinfra* *dracut* *.src.rpm
                tree
            """
        )
    }

    stage("Extract RPM contents") {
        def arches = commonlib.cleanCommaList(params.ARCHES)
        commonlib.shell(
            script: "./extract.sh '${workdir}' '${params.VERSION}' '${arches}'",
        )
    }

    stage("calculate shasum") {
        commonlib.shell(
            script: "cd ${workdir}/${params.VERSION} && sha256sum * > sha256sum.txt",
        )
    }

    stage("Sync to mirror") {
        if (params.DRY_RUN) {
            commonlib.shell(
                script: [
                    "echo 'Would have synced the following to ${mirror}:'",
                    "tree ${workdir}/${params.VERSION}",
                ].join('\n')
            )
        } else {
            sh "tree ${workdir}/${params.VERSION} && cat ${workdir}/${params.VERSION}/sha256sum.txt"
            commonlib.syncDirToS3Mirror("${workdir}/${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/coreos-installer/${params.VERSION}/")
            commonlib.syncDirToS3Mirror("${workdir}/${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/coreos-installer/latest/")
        }
    }

    stage("sign artifacts") {
        if (params.DRY_RUN) {
            echo "Would have signed artifacts"
            return
        }
        release.signArtifacts(
            name: params.VERSION,
            signature_name: "signature-1",
            dry_run: params.DRY_RUN,
            env: "prod",
            key_name: "redhatrelease2",
            arch: "x86_64",
            digest: "",
            client_type: "ocp",
            product: "coreos-installer",
        )

        commonlib.syncDirToS3Mirror("${workdir}/${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/coreos-installer/${params.VERSION}/")
        commonlib.syncDirToS3Mirror("${workdir}/${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/coreos-installer/latest/")

    }

    buildlib.cleanWorkspace()
}

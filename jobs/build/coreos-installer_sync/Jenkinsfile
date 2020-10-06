#!/usr/bin/env groovy
node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    commonlib.describeJob("coreos-installer_sync", """
        <h2>Sync contents of the coreos-installer RPM to mirror</h2>
        http://mirror.openshift.com/pub/openshift-v4/clients/coreos-installer/

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
    buildlib.initialize()
    buildlib.cleanWorkdir(workdir)

    stage("Validate params") {
        if (!params.NVR) {
            error "NVR must be specified"
        }
        if (!params.VERSION) {
            error "VERSION must be specified"
        }
    }

    stage("Download RPM") {
        commonlib.shell(
            script: """
                set -exuo pipefail
                cd ${workdir}
                rm --recursive --force ./*
                brew --quiet download-build ${params.NVR}
                shopt -s nullglob
                rm --force *bootinfra* *.src.rpm
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

    stage("Sync to mirror") {
        def mirror = "use-mirror-upload.ops.rhcloud.com"
        def dir = "/srv/pub/openshift-v4/clients/coreos-installer"

        if (params.DRY_RUN) {
            commonlib.shell(
                script: [
                    "echo 'Would have synced the following to ${mirror}:'",
                    "tree ${workdir}/${params.VERSION}",
                ].join('\n')
            )
            return
        }

        sshagent(['aos-cd-test']) {
            commonlib.shell(
                script: """
                    set -euxo pipefail
                    cd ${workdir}
                    ssh ${mirror} mkdir -p ${dir}
                    scp -r ${params.VERSION} ${mirror}:${dir}/${params.VERSION}
                    if [[ -f ${params.VERSION}/coreos-installer_amd64 ]]; then
                        ssh ${mirror} ln --symbolic --force --no-dereference coreos-installer_amd64 ${dir}/${params.VERSION}/coreos-installer
                    fi
                    ssh ${mirror} ln --symbolic --force --no-dereference ${params.VERSION} ${dir}/latest
                    ssh ${mirror} tree ${dir}
                    ssh ${mirror} /usr/local/bin/push.pub.sh openshift-v4/clients/coreos-installer -v
                """
            )
        }
    }
}

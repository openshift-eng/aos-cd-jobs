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
            description: "Desired version name. Example: v3.0.1",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "LINUX_AMD64_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/helm/3.2.3-4/signed/linux/helm-linux-amd64.tar.gz",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "LINUX_PPC64LE_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/brewroot/vol/rhel-8/packages/helm/3.2.3/4.el8/ppc64le/helm-3.2.3-4.el8.ppc64le.rpm",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "LINUX_S390X_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/brewroot/vol/rhel-8/packages/helm/3.2.3/4.el8/s390x/helm-3.2.3-4.el8.s390x.rpm",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "DARWIN_AMD64_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/helm/3.2.3-4/signed/macos/helm-darwin-amd64.tar.gz",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "WINDOWS_AMD64_BINARIES_LOCATION",
            description: "Example: http://download.eng.bos.redhat.com/staging-cds/developer/helm/3.2.3-4/signed/windows/helm-windows-amd64.exe.tar.gz",
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
                sh "rm -rf ${params.VERSION} && mkdir ${params.VERSION}"
            }
        }
        stage("Download binaries") {
            parallel {
                stage("linux amd64")   { steps { script { download(params.LINUX_AMD64_BINARIES_LOCATION,   params.VERSION) }}}
                stage("linux ppc64le") { steps { script { download(params.LINUX_PPC64LE_BINARIES_LOCATION, params.VERSION) }}}
                stage("linux s390x")   { steps { script { download(params.LINUX_S390X_BINARIES_LOCATION,   params.VERSION) }}}
                stage("darwin amd64")  { steps { script { download(params.DARWIN_AMD64_BINARIES_LOCATION,  params.VERSION) }}}
                stage("windows amd64") { steps { script { download(params.WINDOWS_AMD64_BINARIES_LOCATION, params.VERSION) }}}
            }
        }
        stage("Organize directory") {
            steps {
                sh """
                cd ${params.VERSION} &&

                mv \$(basename -- ${LINUX_PPC64LE_BINARIES_LOCATION}) helm-linux-ppc64le &&
                mv \$(basename -- ${LINUX_S390X_BINARIES_LOCATION}) helm-linux-s390x &&

                tar -zxvf \$(basename -- ${LINUX_AMD64_BINARIES_LOCATION}) &&
                mv helm helm-linux-amd64 &&

                tar -zxvf \$(basename -- ${DARWIN_AMD64_BINARIES_LOCATION}) &&
                mv helm helm-darwin-amd64 &&

                tar -zxvf \$(basename -- ${WINDOWS_AMD64_BINARIES_LOCATION}) &&
                mv helm.exe helm-windows-amd64.exe &&

                rm *.tar.gz &&
                sha256sum * > sha256sum.txt &&

                cd ..
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

def download(path, destination) {
    sh "wget --recursive --no-parent --no-directories --directory-prefix ${destination} ${path}"
}

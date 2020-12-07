#!/usr/bin/env groovy

node {
    checkout scm
    load('pipeline-scripts/commonlib.groovy').describeJob("tkn_sync", """
        -----------------------------------------------
        Sync the Tekton pipeline client (tkn) to mirror
        -----------------------------------------------
        http://mirror.openshift.com/pub/openshift-v4/clients/pipeline/
        Timing: Run manually by request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: 'TKN_VERSION',
            description: 'Example: 1.3.1',
            defaultValue: '',
            trim: true,
        )
        string(
            name: 'BREW_BUILD_ID',
            description: 'Example: 1392607',
            defaultValue: '',
            trim: true,
        )
    }

    stages {
        stage('Validate params') {
            steps {
                script {
                    if (!params.TKN_VERSION) {
                        error 'TKN_VERSION must be specified'
                    }
                    if (!params.BREW_BUILD_ID) {
                        error 'BREW_BUILD_ID must be specified'
                    }
                }
            }
        }
        stage('Download RPMs') {
            steps {
                sh "rm -rf tkn-*.rpm ./usr/share/{,licences}/openshift-pipelines-client-redistributable"
                sh """
                brew buildinfo ${params.BREW_BUILD_ID} \
                | grep redistributable \
                | awk '{print \$1}' \
                | sed -e 's|/mnt/redhat|http://download.eng.bos.redhat.com|' \
                | wget -i -
                """
            }
        }
        stage('Extract binaries from RPMs') {
            steps {
                sh "ls *.rpm | xargs -L1 -I'X' sh -c 'rpm2cpio X | cpio -idm'"
                sh "mv ./usr/share/openshift-pipelines-client-redistributable/* ."
                sh "mv ./usr/share/licenses/openshift-pipelines-client-redistributable/* ."
            }
        }
        stage('Create Tarballs') {
            steps {
                sh "rm -rf ${params.TKN_VERSION} && mkdir ${params.TKN_VERSION}"

                sh "mv tkn-darwin-amd64 tkn && chmod +x tkn"
                sh "tar -czvf ${params.TKN_VERSION}/tkn-macos-amd64-${params.TKN_VERSION}.tar.gz ./{LICENSE,tkn}"

                sh "mv tkn-linux-amd64 tkn && chmod +x tkn"
                sh "tar -czvf ${params.TKN_VERSION}/tkn-linux-amd64-${params.TKN_VERSION}.tar.gz ./{LICENSE,tkn}"

                sh "mv tkn-linux-ppc64le tkn && chmod +x tkn"
                sh "tar -czvf ${params.TKN_VERSION}/tkn-linux-ppc64le-${params.TKN_VERSION}.tar.gz ./{LICENSE,tkn}"

                sh "mv tkn-linux-s390x tkn && chmod +x tkn"
                sh "tar -czvf ${params.TKN_VERSION}/tkn-linux-s390x-${params.TKN_VERSION}.tar.gz ./{LICENSE,tkn}"

                sh "mv tkn-windows-amd64.exe tkn.exe"
                sh "zip -j ${params.TKN_VERSION}/tkn-windows-amd64-${params.TKN_VERSION}.zip ./{LICENSE,tkn.exe}"
            }
        }
        stage('Calculate sha256sum') {
            steps {
                sh "cd ${params.TKN_VERSION} && sha256sum * > sha256sum.txt"
            }
        }
        stage('Sync to mirror') {
            steps {
                sh "tree ${params.TKN_VERSION} ; cat ${params.TKN_VERSION}/sha256sum.txt"
                sshagent(['aos-cd-test']) {
                    sh "tree ${params.TKN_VERSION}"
                    sh "cat ${params.TKN_VERSION}/sha256sum.txt"
                    sh "scp -r ${params.TKN_VERSION} use-mirror-upload:/srv/pub/openshift-v4/clients/pipeline/"
                    sh "ssh use-mirror-upload ln --symbolic --force --no-dereference ${params.TKN_VERSION} /srv/pub/openshift-v4/clients/pipeline/latest"
                    sh 'ssh use-mirror-upload /usr/local/bin/push.pub.sh openshift-v4/clients/pipeline -v'
                }
            }
        }
    }
}

def download(url) {
    sh "wget --directory-prefix ${params.TKN_VERSION} ${url}"
}

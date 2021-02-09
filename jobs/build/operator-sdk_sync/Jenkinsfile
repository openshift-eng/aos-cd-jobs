node {
    checkout scm
    commonlib = load('pipeline-scripts/commonlib.groovy')
    commonlib.describeJob("operator-sdk_sync", """
        <h2>Sync operator-sdk to mirror</h2>
        <b>Timing</b>: Manually, upon request. Expected to happen once every y-stream and
        sporadically on z-stream releases.
    """)
    imagePath = 'registry-proxy.engineering.redhat.com/rh-osbs/openshift-ose-operator-sdk'
}

pipeline {
    agent any

    options {
        disableResume()
        skipDefaultCheckout()
    }

    parameters {
        string(
            name: 'OCP_VERSION',
            description: 'Under which directory to place the binaries.<br/>' +
                         'Examples:<br/>' +
                         '<ul>' +
                         '<li>4.7.0</li>' +
                         '<li>4.7.0-rc.0</li>' +
                         '</ul>',
            defaultValue: '',
            trim: true,
        )
        string(
            name: 'BUILD_TAG',
            description: 'Build of ose-operator-sdk from which the contents should be extracted.<br/>' +
                         'Examples:<br/>' +
                         '<ul>' +
                         '<li>v4.7.0-202101261648.p0</li>' +
                         '<li>v4.7.0</li>' +
                         '<li>v4.7</li>' +
                         '</ul>',
            defaultValue: '',
            trim: true,
        )
    }

    stages {
        stage('pre-flight') {
            steps {
                script {
                    if (!params.OCP_VERSION) {
                        error 'OCP_VERSION must be specified'
                    }
                    if (!params.BUILD_TAG) {
                        error 'BUILD_TAG must be specified'
                    }
                    sdkVersion = ''
                    buildvmArch = sh(script: 'arch', returnStdout: true).trim()
                    manifestList = readJSON(
                        text: sh(
                            script: "skopeo inspect --raw docker://${imagePath}:${params.BUILD_TAG}",
                            returnStdout: true,
                        )
                    ).manifests
                }
            }
        }
        stage('extract binaries') {
            steps {
                script {
                    manifestList.each {
                        def sdkArch = it.platform.architecture == 'amd64' ? 'x86_64' : it.platform.architecture

                        sh "rm -rf ./${sdkArch} && mkdir ./${sdkArch}"

                        dir("./${sdkArch}") {
                            sh "oc image extract ${imagePath}@${it.digest} --path /usr/local/bin/operator-sdk:. --confirm"
                            sh "chmod +x operator-sdk"

                            if (buildvmArch == sdkArch) {
                                def sdkVersionRaw = sh(script: './operator-sdk version', returnStdout: true)
                                sdkVersion = (sdkVersionRaw =~ /operator-sdk version: "([^"]+)"/).findAll()[0][1]
                            }
                        }
                    }
                    currentBuild.displayName = "${params.OCP_VERSION}/${sdkVersion}"
                    currentBuild.description = "${params.BUILD_TAG}"
                }
            }
        }
        stage('sync tarballs') {
            steps {
                script {
                    manifestList.each {
                        def arch = it.platform.architecture == 'amd64' ? 'x86_64' : it.platform.architecture

                        dir("./${arch}") {
                            def tarballFilename = "operator-sdk-${sdkVersion}-linux-${arch}.tar.gz"
                            sh "tar -csvf ${tarballFilename} ./operator-sdk"

                            sshagent(['aos-cd-test']) {
                                sh "ssh use-mirror-upload.ops.rhcloud.com -- mkdir -p /srv/pub/openshift-v4/${arch}/clients/operator-sdk/${params.OCP_VERSION}"
                                sh "scp ${tarballFilename} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/${arch}/clients/operator-sdk/${params.OCP_VERSION}"
                                sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/${arch}/clients/operator-sdk -v"
                            }

                        }
                    }
                }
            }
        }
    }
}

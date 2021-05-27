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

                    currentBuild.description = "${params.BUILD_TAG}"
                    currentBuild.displayName = "${params.OCP_VERSION}"

                    archList = ['x86_64']
                    readJSON(
                        text: sh(
                            script: "skopeo inspect --raw docker://${imagePath}:${params.BUILD_TAG}",
                            returnStdout: true,
                        )
                    ).manifests.each {
                        // We want x86_64 to be the first in the list, as that will be used to extract the
                        // Operator SDK version, which is used while naming the files.
                        def sdkArch = commonlib.brewArchForGoArch(it.platform.architecture)
                        def data = [arch: sdkArch, digest: it.digest]
                        println("data: ${data}")

                        if (archList.contains(sdkArch)) {
                            def ind = archList.findIndexOf({it == 'x86_64'})
                            archList.set(ind, data)
                        } else {
                            archList.add(data)
                        }
                    }
                    echo "archList: ${archList}"
                }
            }
        }
        stage('extract binaries') {
            steps {
                script {
                    archList.each {
                        sh "rm -rf ./${it.arch} && mkdir ./${it.arch}"
                        dir("./${it.arch}") {
                            sh "oc image extract ${imagePath}@${it.digest} --path /usr/local/bin/operator-sdk:. --confirm"
                            sh "chmod +x operator-sdk"

                            if (it.arch == buildvmArch) {
                                def sdkVersionRaw = sh(script: './operator-sdk version', returnStdout: true)
                                sdkVersion = (sdkVersionRaw =~ /operator-sdk version: "([^"]+)"/).findAll()[0][1]
                                currentBuild.displayName += "/${sdkVersion}"
                            }

                            def tarballFilename = "operator-sdk-${sdkVersion}-linux-${it.arch}.tar.gz"
                            sh "tar --create --preserve-order --gzip --verbose --file ${tarballFilename} ./operator-sdk"
                            sh "rm -f ./operator-sdk"

                            // Extract darwin binaries
                            if (it.arch == "x86_64") {
                                sh "oc image extract ${imagePath}@${it.digest} --path /usr/share/operator-sdk/mac/operator-sdk:. --confirm"
                                sh "chmod +x operator-sdk"
                                tarballFilename = "operator-sdk-${sdkVersion}-darwin-${it.arch}.tar.gz"
                                sh "tar --create --preserve-order --gzip --verbose --file ${tarballFilename} ./operator-sdk"
                                sh "rm -f ./operator-sdk"
                            }

                        }
                    }
                }
            }
        }
        stage('sync tarballs') {
            steps {
                script {
                    sh "pwd"
                    archList.each {
                        def arch = it.arch
                        sh "tree ${arch}"
                        dir("./${arch}") {
                            sshagent(['aos-cd-test']) {
                                sh "ssh use-mirror-upload.ops.rhcloud.com -- mkdir -p /srv/pub/openshift-v4/${arch}/clients/operator-sdk/${params.OCP_VERSION}"
                                sh "scp -- *.tar.gz use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/${arch}/clients/operator-sdk/${params.OCP_VERSION}"
                                sh "ssh use-mirror-upload.ops.rhcloud.com -- ln --symbolic --force --no-dereference ${params.OCP_VERSION} /srv/pub/openshift-v4/${arch}/clients/operator-sdk/latest"
                                sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/${arch}/clients/operator-sdk -v"
                            }
                        }
                    }
                }
            }
        }
    }
}

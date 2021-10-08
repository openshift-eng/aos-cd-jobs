node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.describeJob("butane_sync", """
        ------------------------------
        Sync Butane binaries to mirror
        ------------------------------
        Sync butane binaries to mirror.openshift.com.
        (formerly the Fedora CoreOS Config Transpiler, FCCT)

        http://mirror.openshift.com/pub/openshift-v4/x86_64/clients/butane/

        Timing: This is only ever run by humans, upon request.
    """)
}

pipeline {
    agent any
    options { disableResume() }

    parameters {
        string(
            name: "NVR",
            description: "NVR of the brew build from which binaries should be extracted.<br/>" +
                         "Example: butane-0.11.0-3.rhaos4.8.el8",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "VERSION",
            description: "Under which directory to place the binaries.<br/>" +
                         "Example: v0.11.0",
            defaultValue: "",
            trim: true,
        )
    }

    stages {
        stage("validate params") {
            steps {
                script {
                    if (!params.NVR) {
                        error "NVR must be specified"
                    }
                    if (!params.VERSION) {
                        error "VERSION must be specified"
                    }
                }
            }
        }
        stage("download build") {
            steps {
                script {
                    commonlib.shell(
                        script: """
                        rm -rf ./${params.VERSION}
                        mkdir -p ./${params.VERSION}
                        cd ./${params.VERSION}
                        brew download-build ${params.NVR}
                        tree
                        """
                    )
                }
            }
        }
        stage("extract binaries") {
            steps {
                dir("./${params.VERSION}") {
                    script {
                        commonlib.shell(
                            script: """
                            rpm2cpio *.aarch64.rpm | cpio -idm ./usr/bin/butane
                            mv ./usr/bin/butane ./butane-aarch64
                            rm -rf *.aarch64.rpm ./usr
                            """
                        )
                        commonlib.shell(
                            script: """
                            rpm2cpio *.noarch.rpm | cpio -idm ./usr/share/butane-redistributable/*
                            mv ./usr/share/butane-redistributable/* .
                            rm -rf *.noarch.rpm ./usr
                            """
                        )
                        commonlib.shell(
                            script: """
                            rpm2cpio *.ppc64le.rpm | cpio -idm ./usr/bin/butane
                            mv ./usr/bin/butane ./butane-ppc64le
                            rm -rf *.ppc64le.rpm ./usr
                            """
                        )
                        commonlib.shell(
                            script: """
                            rpm2cpio *.s390x.rpm | cpio -idm ./usr/bin/butane
                            mv ./usr/bin/butane ./butane-s390x
                            rm -rf *.s390x.rpm ./usr
                            """
                        )
                        commonlib.shell(
                            script: """
                            rpm2cpio *.x86_64.rpm | cpio -idm ./usr/bin/butane
                            mv ./usr/bin/butane ./butane-amd64
                            ln -s ./butane-amd64 ./butane
                            rm -rf *.x86_64.rpm ./usr
                            """
                        )
                    }
                    sh "rm *.src.rpm"
                }
            }
        }
        stage("calculate shasum") {
            steps {
                sh "cd ./${params.VERSION} && sha256sum * > sha256sum.txt"
            }
        }
        stage("sync to mirror") {
            steps {
                sh "tree ./${params.VERSION} && cat ./${params.VERSION}/sha256sum.txt"
                script {
                    commonlib.syncDirToS3Mirror("./${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/butane/${params.VERSION}/")
                    commonlib.syncDirToS3Mirror("./${params.VERSION}/", "/pub/openshift-v4/x86_64/clients/butane/latest/")
                }
                sshagent(["aos-cd-test"]) {
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- mkdir -p /srv/pub/openshift-v4/x86_64/clients/butane"
                    sh "scp -r ./${params.VERSION} use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/x86_64/clients/butane/"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- ln --symbolic --force --no-dereference ${params.VERSION} /srv/pub/openshift-v4/x86_64/clients/butane/latest"
                    sh "ssh use-mirror-upload.ops.rhcloud.com -- /usr/local/bin/push.pub.sh openshift-v4/x86_64/clients/butane -v"
                }
            }
        }
    }
}

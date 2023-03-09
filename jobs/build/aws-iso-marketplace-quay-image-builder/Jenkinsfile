#!/usr/bin/env groovy
node {
    checkout scm
    commonlib = load("pipeline-scripts/commonlib.groovy")
    commonlib.describeJob("aws-iso-marketplace-quay-image-builder", """
        --------------------------
        Constructs an AMI for a fully disconnected and self-contained install.
        --------------------------
        https://issues.redhat.com/browse/ART-5431
    """)
}

pipeline {
    agent any
    options {
        disableConcurrentBuilds()
        disableResume()
        buildDiscarder(
          logRotator(
            artifactDaysToKeepStr: '60',
            daysToKeepStr: '60')
        )
    }

    parameters {
        string(
            name: "CINCINNATI_OCP_VERSION",
            description: "A version of OpenShift in the candidate channel from which to create an AMI (e.g. 4.10.36).",
            defaultValue: "",
            trim: true,
        )
        string(
            name: "QUAY_IMAGE_BUILDER_FORK",
            description: "Which org/user contains the quay-image-builder repo to utilize",
            defaultValue: "openshift",
            trim: true,
        )
        string(
            name: "QUAY_IMAGE_BUILDER_COMMITISH",
            description: "A commitish to use for github.com/[QUAY_IMAGE_BUILDER_FORK]/quay-image-builder",
            defaultValue: "main",
            trim: true,
        )
        booleanParam(
            name: 'BUILD_RUNNER_IMAGE',
            defaultValue: false,
            description: "The builder is run in a docker container. Select true to spend time building/rebuilding this image."
        )
        booleanParam(
            name: 'BUILD_TEMPLATE_AMI',
            defaultValue: false,
            description: "The template AMI construct that speeds up the creation of the final deliverable. It installs packages and configures hundreds of elements of the system so that the final image build process does not need to. It should only need to be updated if the template changes or packages are taking a long time to be updated in final AMI builds."
        )
        booleanParam(
            name: 'PACKER_DEBUG',
            defaultValue: false,
            description: "Set to true to pass -debug to packer (this will write ssh keys out to the quay-image-builder workspace directory) and to increase ssh timeout to 30m."
        )
        booleanParam(name: 'MOCK', defaultValue: false)
    }

    stages {
        stage("Validate Params") {
            steps {
                script {
                    if (!params.CINCINNATI_OCP_VERSION) {
                        error "CINCINNATI_OCP_VERSION must be specified"
                    }
                }
            }
        }

        stage("Wait for Cincy") {
            steps {
                script {
                    // Before quay-image-builder can work, the release must be present in Cincinnati.
                    (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.CINCINNATI_OCP_VERSION)

                    // Everything starts here, so it is our early chance to find a release.
                    channel = "candidate-${major}.${minor}"
                    attempt = 0
                    retry(60) {
                        if (attempt > 0) {
                            echo "Waiting for up to 1 hour for version"
                            sleep(unit: "MINUTES", time: 1)
                        }
                        // This will throw an exception if the desired version is not in Cincinnati.
                        sh("""
                        curl -sH 'Accept:application/json' 'https://api.openshift.com/api/upgrades_info/v1/graph?channel=${channel}' | jq .nodes | grep '"${params.CINCINNATI_OCP_VERSION}"'
                        """)
                        attempt++
                    }
                }
            }
        }

        stage("Clone Builder") {
            steps {
                script {
                    sh """
                    rm -rf quay-image-builder
                    git clone https://github.com/openshift/quay-image-builder
                    cd quay-image-builder
                    git checkout ${params.QUAY_IMAGE_BUILDER_COMMITISH}
                    """
                    withCredentials([file(credentialsId: 'rh-cdn.pem', variable: 'CERT_FILE')]) {
                        dir(env.WORKSPACE) {
                            // Ensure that the rh-cdn.pem is in the same directory as the build_template.sh script
                            sh '''
                                cp $CERT_FILE quay-image-builder/rh-cdn.pem
                                chmod +r quay-image-builder/rh-cdn.pem
                            '''
                        }
                    }
                }
            }
        }

        stage("Runner Image") {
            steps {
                script {
                    if (params.BUILD_RUNNER_IMAGE) {
                        commonlib.shell("docker build . -f runner-image.Dockerfile -t runner-image")
                    } else {
                        echo "Skipping the build or rebuild of the runner-image"
                    }
                }
            }
        }

        stage("Build Template AMI") {
            steps {
                script {
                    if (params.BUILD_TEMPLATE_AMI) {
                        // Establish the credentials necessary to build the AMI in osd-art / us-east-2 region.
                        withCredentials([aws(credentialsId: 'quay-image-builder-aws', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                            dir("quay-image-builder") {
                                commonlib.shell("""
                                    # See https://github.com/openshift/quay-image-builder for environment variable description.
                                    # SOURCE_AMI derived from https://issues.redhat.com/browse/ART-5898
                                    # EIP_ALLOC was created in us-east-2 osd-art account specifically for this purpose and goes unused otherwise.
                                    docker run --rm -v ${env.WORKSPACE}/quay-image-builder:/quay-image-builder:z -e PACKER_DEBUG=${params.PACKER_DEBUG} -e EIP_ALLOC=eipalloc-03243b75c8ef5f56b -e SOURCE_AMI=ami-0bab7c98f46febc77 -e IAM_INSTANCE_PROFILE=ec2-instance-profile-for-quay-image-builder -e OCP_VER=${params.CINCINNATI_OCP_VERSION} -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION=us-east-2 -v $HOME/.docker/:/pullsecret:z -e PULL_SECRET=/pullsecret/config.json --entrypoint /quay-image-builder/build_template.sh runner-image
                                """)
                            }
                        }
                    } else {
                        echo "Skipping the template AMI build"
                    }
                }
            }
        }

        stage("Run Build") {
            steps {
                script {
                    // Establish the credentials necessary to build the AMI in osd-art / us-east-2 region.
                    withCredentials([
                                        aws(credentialsId: 'quay-image-builder-aws', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'),
                                        string(credentialsId: 'ICMP_AWS_SHARE_ACCOUNT', variable: 'SHARE_ACCOUNT'),
                                        string(credentialsId: 'ICMP_AWS_SHARE_DEV_ACCOUNT', variable: 'DEV_SHARE_ACCOUNT')
                    ]) {
                        dir("quay-image-builder") {
                            commonlib.shell("""
                                # See https://github.com/openshift/quay-image-builder for environment variable description.
                                # SOURCE_AMI derived from https://issues.redhat.com/browse/ART-5898
                                # EIP_ALLOC was created in us-east-2 osd-art account specifically for this purpose and goes unused otherwise.
                                docker run --rm -v ${env.WORKSPACE}/quay-image-builder:/quay-image-builder:z -e PACKER_DEBUG=${params.PACKER_DEBUG} -e EIP_ALLOC=eipalloc-03243b75c8ef5f56b -e SOURCE_AMI=ami-0bab7c98f46febc77 -e IAM_INSTANCE_PROFILE=ec2-instance-profile-for-quay-image-builder -e IMAGESET_CONFIG_TEMPLATE=/quay-image-builder/imageset-config.yaml -e OCP_VER=${params.CINCINNATI_OCP_VERSION} -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION=us-east-2 -v $HOME/.docker/:/pullsecret:z -e PULL_SECRET=/pullsecret/config.json --entrypoint /quay-image-builder/build.sh runner-image
                            """)
                            // Packer, involved by build.sh, will create a machine-readable packer.log. Look
                            // for a line like:
                            // 1674670955,amazon-ebs,artifact,0,id,us-east-2:ami-xxxxxxxxxxxxxxxxx
                            ami_info = sh(returnStdout: true, script: "cat packer.log | awk -F, '\$0 ~/artifact,0,id/ {print \$6}'").trim() // should look like us-east-2:ami-xxxxxxxxxxxxxxxxx
                            (region, ami_id) = ami_info.split(':')

                            // Share with staging account https://issues.redhat.com/browse/ART-5510
                            commonlib.shell("""
                            aws ec2 modify-image-attribute --region ${region} --image-id ${ami_id} --launch-permission "Add=[{UserId=${SHARE_ACCOUNT}}]"
                            """)
                            // Share with Dev staging account https://issues.redhat.com/browse/ART-5510
                            commonlib.shell("""
                            aws ec2 modify-image-attribute --region ${region} --image-id ${ami_id} --launch-permission "Add=[{UserId=${DEV_SHARE_ACCOUNT}}]"
                            """)
                        }
                    }
                }
            }
        }
    }
}


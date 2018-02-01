#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

// Expose properties for a parameterized build
properties(
        [
                disableConcurrentBuilds(),
                [$class: 'ParametersDefinitionProperty',
                 parameterDefinitions:
                         [
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'openshift-build-1', description: 'Jenkins agent node', name: 'TARGET_NODE'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-cicd@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                                 [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Force rebuild even if no changes are detected?', name: 'FORCE_REBUILD'],
                                 [$class: 'hudson.model.ChoiceParameterDefinition',
                                    choices: "openshift-enterprise\norigin",
                                    defaultValue: 'openshift-enterprise',
                                    description: '''origin                    Openshift origin  <br>
                                                    openshift-enterprise      Openshift Enterpriseonline <br>
                                    ''',
                                    name: 'DEPLOYMENT_TYPE'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'cicd_build', description: 'Specify a name that will be used for the VPC. Also used for VPC and other settings', name: 'VPC_NAME'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'us-east-1c', description: 'Specify an availability zone for the AMI build instance to use.', name: 'AZ_NAME'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'default', description: 'Specify a security group name for the AMI build instance to use.', name: 'SG_NAME'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: '3.9.0', description: 'Openshift Version (matches version in branch name for release builds)', name: 'OPENSHIFT_VERSION'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: '0.0.0.git.0.1234567.el7', description: 'Release version (The release version number)', name: 'OPENSHIFT_RELEASE'],
                                 [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?.', name: 'MOCK'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'ami-ac0863d6', description: 'Base AMI id to build from.', name: 'BASE_AMI_ID'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'cicd_openshift_node_ami_build', description: 'Base AMI instance name.', name: 'BASE_AMI_NAME'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'ami_builder_key', description: 'Name of the AWS SSH key user to use.', name: 'AWS_SSH_KEY_USER'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'https://mirror.openshift.com/enterprise/online-int/latest/x86_64/os/', description: 'Base url for repository.', name: 'YUM_BASE_URL'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'False', description: 'Enable CRIO in Openshift for the AMI build.', name: 'USE_CRIO'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'docker.io/runcom/cri-o-system-container:v3.8', description: 'CRIO system container override image.', name: 'CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE'],
                                 [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'master', description: 'openshift-ansible checkout point.', name: 'OPENSHIFT_ANSIBLE_CHECKOUT'],
                         ]
                ],
        ]
)

if ( MOCK.toBoolean() ) {
    error( "Ran in mock mode to pick up any new parameters" )
}

node(TARGET_NODE) {
    try {
        set_workspace()
        def buildlib = null
        def build_date = new Date().format('yyyyMMddHHmm')
        stage('clone') {
            checkout scm
            buildlib = load('pipeline-scripts/buildlib.groovy')
            dir('openshift-ansible') {
                git 'https://github.com/openshift/openshift-ansible.git'
                //sh "git checkout ${OPENSHIFT_ANSIBLE_CHECKOUT}"
                //sh "git pull"
            }
        }
        stage('venv') {
            sh '''
[ -e env/ ] || virtualenv env/
env/bin/pip install --upgrade pip
env/bin/pip install --upgrade ansible boto boto3
'''
        }
        stage('build') {
            // create the provisioning_vars.yml file to use as inventory
            writeFile(
                file: 'provisioning_vars.yml',
                text: """---
openshift_node_use_instance_profiles: True
openshift_aws_create_vpc: False
openshift_deployment_type: ${DEPLOYMENT_TYPE}
openshift_clusterid: default
openshift_aws_vpc_name: ${VPC_NAME}
openshift_aws_region: us-east-1
openshift_aws_build_ami_ssh_user: root
openshift_aws_build_ami_group: ${SG_NAME}
openshift_aws_subnet_az: ${AZ_NAME}
openshift_aws_base_ami: ${BASE_AMI_ID}
openshift_aws_ssh_key_name: ${AWS_SSH_KEY_USER}
openshift_pkg_version: "-${OPENSHIFT_VERSION}"
openshift_cloudprovider_kind: aws
openshift_aws_base_ami_name: ${BASE_AMI_NAME}
openshift_use_crio: ${USE_CRIO}
openshift_crio_systemcontainer_image_override: "${CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE}"
openshift_additional_repos: [{'name': 'openshift-repo', 'id': 'openshift-repo',  'baseurl': '${env.YUM_BASE_URL}', 'enabled': 'yes', 'gpgcheck': 0, 'sslverify': 'no', 'sslclientcert': '/var/lib/yum/client-cert.pem', 'sslclientkey': '/var/lib/yum/client-key.pem', 'gpgkey': 'https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-release https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-beta https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-openshifthosted'},{'sslverify': False, 'name': 'fastdata', 'sslclientkey': '/var/lib/yum/client-key.pem', 'enabled': True, 'gpgkey': 'https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-release https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-beta https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-openshifthosted', 'sslclientcert': '/var/lib/yum/client-cert.pem', 'baseurl': 'https://mirror.ops.rhcloud.com/enterprise/rhel/rhel-7-fast-datapath-rpms/', 'file': 'fastdata-ovs', 'gpgcheck': False, 'description': 'Fastdata provides the official builds of OVS OpenShift supports'}]
oreg_url: 'registry.reg-aws.openshift.com:443/openshift3/ose-\${component}:\${version}'
container_runtime_docker_storage_type: overlay2
container_runtime_docker_storage_setup_device: xvdb
docker_storage_path: /var/lib/containers/docker
docker_storage_size: 200G
openshift_aws_node_group_config_node_volumes:
- device_name: /dev/sda1
  volume_size: 30
  device_type: gp2
  delete_on_termination: True
- device_name: /dev/sdb
  volume_size: 200
  device_type: gp2
  delete_on_termination: True
openshift_aws_ami_tags:
  bootstrap: "true"
  openshift-created: "true"
  parent: "${BASE_AMI_ID}"
  openshift_version: "${OPENSHIFT_VERSION}"
  openshift_short_version: "${OPENSHIFT_VERSION.substring(0,3)}"
  openshift_release: "${OPENSHIFT_RELEASE}"
  openshift_version_release: "${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE}"
  build_date: "${build_date}"
openshift_aws_ami_name: "aos-${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE.split('.git')[0]}-${build_date}"
""")
            sh 'cat provisioning_vars.yml'
            withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'pull-creds.reg-aws',
                              usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD']]) {
                sh 'oc login --config=.kube/reg-aws -u $USERNAME -p $PASSWORD https://api.reg-aws.openshift.com'
                sh 'echo "oreg_auth_user: $USERNAME" >> provisioning_vars.yml'
                sh '#!/bin/sh -e\n' + 'echo "oreg_auth_password: $(oc --config=.kube/reg-aws whoami -t)" >> provisioning_vars.yml'

                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'ami-build-creds']]) {
                    withEnv(['ANSIBLE_HOST_KEY_CHECKING=False']) {
                        sshagent([AWS_SSH_KEY_USER]) {
                            buildlib.with_virtualenv('env') {
                                sh 'ansible-playbook openshift-ansible/playbooks/aws/openshift-cluster/build_ami.yml -e @provisioning_vars.yml -vvv'
                                sh "ansible-playbook copy_ami_to_regions.yml -e cli_ami_name='aos-${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE.split('.git')[0]}-${build_date}' -vvv"
                            }
                        }
                    }
                }
            }
        }
    } catch ( err ) {
        // Replace flow control with: https://jenkins.io/blog/2016/12/19/declarative-pipeline-beta/ when available
        mail(to: "${MAIL_LIST_FAILURE}",
                from: 'aos-cd@redhat.com',
                subject: "Error building aws ami",
                body: """Encoutered an error while running build_ami.yml: ${err}


Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }
}

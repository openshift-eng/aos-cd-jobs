#!/usr/bin/env groovy

// https://issues.jenkins-ci.org/browse/JENKINS-33511
def set_workspace() {
    if(env.WORKSPACE == null) {
        env.WORKSPACE = pwd()
    }
}

def convert_aws_account_property_to_ansible_arg(ansible_arg, ansible_value) {
    def created_ansible_arg = ''
    if (!ansible_value.isEmpty()) {
        created_ansible_arg = " -e ${ansible_arg}=${ansible_value.trim()} "
    }

    return created_ansible_arg
}

def build_aws_tag_args(ami_search_tags){
    def tag_args = ''
    if (!ami_search_tags.isEmpty()) {
        def tmp_tag_args = ""
        def split_args = ami_search_tags.split(',')
        split_args.each {
            tmp_tag_args += " -t " + it
        }
        tag_args = tmp_tag_args
     }

    return tag_args
}

def write_ansible_var_file(build_date, ami_id, jenkins_oreg_auth_user, jenkins_oreg_auth_password){
    // create the provisioning_vars.yml file to use as inventory
    writeFile(file: 'provisioning_vars.yml', text: """---
openshift_aws_base_ami: ${ami_id}
openshift_node_use_instance_profiles: True
openshift_aws_create_vpc: False
openshift_deployment_type: ${DEPLOYMENT_TYPE}
openshift_clusterid: default
openshift_aws_vpc_name: ${VPC_NAME}
openshift_aws_region: ${AWS_REGION}
openshift_aws_build_ami_ssh_user: root
openshift_aws_build_ami_group: ${SG_NAME}
openshift_aws_subnet_az: ${AZ_NAME}
openshift_aws_ssh_key_name: ${AWS_SSH_KEY_USER}
openshift_pkg_version: "-${OPENSHIFT_VERSION}"
openshift_cloudprovider_kind: aws
openshift_aws_base_ami_name: ${BASE_AMI_NAME}
openshift_use_crio: ${USE_CRIO}
openshift_crio_use_rpm: True
# openshift_crio_systemcontainer_image_override is not needed when using the RPM
openshift_crio_systemcontainer_image_override: "${CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE}"
openshift_additional_repos: [{'name': 'openshift-repo', 'id': 'openshift-repo',  'baseurl': '${env.YUM_BASE_URL}', 'enabled': 'yes', 'gpgcheck': 0, 'sslverify': 'no', 'sslclientcert': '/var/lib/yum/client-cert.pem', 'sslclientkey': '/var/lib/yum/client-key.pem', 'gpgkey': 'https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-release https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-beta https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-openshifthosted'},{'sslverify': False, 'name': 'fastdata', 'sslclientkey': '/var/lib/yum/client-key.pem', 'enabled': True, 'gpgkey': 'https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-release https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-beta https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-openshifthosted', 'sslclientcert': '/var/lib/yum/client-cert.pem', 'baseurl': 'https://mirror.ops.rhcloud.com/enterprise/rhel/rhel-7-fast-datapath-rpms/', 'file': 'fastdata-ovs', 'gpgcheck': False, 'description': 'Fastdata provides the official builds of OVS OpenShift supports'}]
oreg_url: 'registry.reg-aws.openshift.com:443/openshift3/ose-\${component}:\${version}'
container_runtime_docker_storage_type: overlay2
container_runtime_docker_storage_setup_device: xvdb
docker_storage_path: /var/lib/containers
docker_storage_size: 200G
openshift_docker_options: '--log-driver=json-file --log-opt max-size=50m'
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
  parent: "{{ openshift_aws_base_ami }}"
  openshift_version: "${OPENSHIFT_VERSION}"
  openshift_short_version: "${OPENSHIFT_VERSION.substring(0,3)}"
  openshift_release: "${OPENSHIFT_RELEASE}"
  openshift_version_release: "${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE}"
  build_date: "${build_date}"
  base_ami: "false"
openshift_aws_ami_name: "aos-${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE.split('.git')[0]}-${build_date}"
oreg_auth_user: ${jenkins_oreg_auth_user}
oreg_auth_password: ${jenkins_oreg_auth_password}
openshift_aws_copy_base_ami_tags: True
container_runtime_oci_umounts:
- '/var/lib/containers/storage/*'
- '/run/containers/storage/*'
- '/var/lib/origin/*'
""")

    sh 'cat provisioning_vars.yml'
}

// Expose properties for a parameterized build
properties(
        [
            disableConcurrentBuilds(),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions:
                [
                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'openshift-build-1',
                     description: 'Jenkins agent node',
                     name: 'TARGET_NODE'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'aos-cicd@redhat.com',
                     description: 'Success Mailing List',
                     name: 'MAIL_LIST_SUCCESS'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'jupierce@redhat.com,bbarcaro@redhat.com,mwoodson@redhat.com',
                     description: 'Failure Mailing List',
                     name: 'MAIL_LIST_FAILURE'],

                    [$class: 'hudson.model.BooleanParameterDefinition',
                     defaultValue: false,
                     description: 'Force rebuild even if no changes are detected?',
                     name: 'FORCE_REBUILD'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: '3.9.0',
                     description: 'Openshift Version (matches version in branch name for release builds)',
                     name: 'OPENSHIFT_VERSION'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: '0.0.0.git.0.1234567.el7',
                     description: 'Release version (The release version number)',
                     name: 'OPENSHIFT_RELEASE'],

                    [$class: 'hudson.model.ChoiceParameterDefinition',
                     choices: "openshift-enterprise\norigin",
                     defaultValue: 'openshift-enterprise',
                     description: 'origin - Openshift origin\nopenshift-enterprise - Openshift Enterpriseonline',
                     name: 'DEPLOYMENT_TYPE'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'https://mirror.openshift.com/enterprise/online-int/latest/x86_64/os/',
                     description: 'Base url for repository.',
                     name: 'YUM_BASE_URL'],

                    [$class: 'hudson.model.BooleanParameterDefinition',
                     defaultValue: true,
                     description: 'Enable CRIO in Openshift for the AMI build.',
                     name: 'USE_CRIO'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'docker.io/runcom/cri-o-system-container:v3.8',
                     description: 'CRIO system container override image.',
                     name: 'CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'https://github.com/openshift/openshift-ansible.git',
                     description: 'openshift-ansible repo URL.',
                     name: 'OPENSHIFT_ANSIBLE_REPO_URL'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'master',
                     description: 'openshift-ansible checkout reference.',
                     name: 'OPENSHIFT_ANSIBLE_CHECKOUT'],

                    // Parameters to search for AMI to use
                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'operating_system=RedHat,standard=true,base_ami=true',
                     description: 'Comma delimited tags (K=V) to use to find the base AMI to use\n  NOTE: This option is overrididen by specifying the BASE_AMI_ID\n  NOTE: "base_ami=true" is probably necessary; otherwise a previous built ami will be used, and no packages will be updated!',
                     name: 'AMI_SEARCH_TAGS'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: '',
                     description: 'Base AMI id to build from.\nNOTE: By default the job will search for the latest AMI based on the AMI Search Tags. If this is provided, it will override the search tags provided',
                     name: 'BASE_AMI_ID'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: '531415883065,704252977135,639866565627,925374498059',
                     description: 'Comma delimited list of AWS accounts to share the image with.\nNOTE: Currently this only shares the AMI in the AWS_REGION defined.\n   531415883065 - Openshift DevEnv AWS Account\n   704252977135 - free-int AWS Account\n   639866565627 - Ops Test AWS Account\n   925374498059 - Perf Testing Account',
                     name: 'AMI_SHARE_ACCOUNTS'],

                    // AWS Settings, these probably shouldn't change too often
                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'us-east-1',
                     description: 'AWS Region to use',
                     name: 'AWS_REGION'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'cicd_openshift_node_ami_build',
                     description: 'Base AMI instance name.',
                     name: 'BASE_AMI_NAME'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'ami_builder_key',
                     description: 'Name of the AWS SSH key user to use.',
                     name: 'AWS_SSH_KEY_USER'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'cicd_build',
                     description: 'Specify a name that will be used for the VPC. Also used for VPC and other settings',
                     name: 'VPC_NAME'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'us-east-1c',
                     description: 'Specify an availability zone for the AMI build instance to use.',
                     name: 'AZ_NAME'],

                    [$class: 'hudson.model.StringParameterDefinition',
                     defaultValue: 'default',
                     description: 'Specify a security group name for the AMI build instance to use.',
                     name: 'SG_NAME'],

                    // Mock
                    [$class: 'BooleanParameterDefinition',
                     defaultValue: false,
                     description: 'Mock run to pickup new Jenkins parameters?.',
                     name: 'MOCK'],
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
                git url: "${OPENSHIFT_ANSIBLE_REPO_URL}", branch: "${OPENSHIFT_ANSIBLE_CHECKOUT}"
            }
        }
        stage('venv') {
            sh '''
[ -e env/ ] || virtualenv env/
env/bin/pip install --upgrade pip
env/bin/pip install --upgrade 'ansible<2.5' boto boto3
'''
        }
        stage('build') {

            currentBuild.displayName = "#${currentBuild.number} - ${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE}"

            // get the reg-aws credentials
            withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: 'pull-creds.reg-aws',
                              usernameVariable: 'REG_AWS_USERNAME', passwordVariable: 'REG_AWS_PASSWORD']]) {
                sh 'oc login --config=.kube/reg-aws -u $REG_AWS_USERNAME -p $REG_AWS_PASSWORD https://api.reg-aws.openshift.com'

                jenkins_oreg_auth_user = env.REG_AWS_USERNAME
                jenkins_oreg_auth_password = sh(returnStdout: true, script: 'oc --config=.kube/reg-aws whoami -t').trim()
            }

            withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'ami-build-creds']]) {
                withEnv(['ANSIBLE_HOST_KEY_CHECKING=False']) {
                    sshagent([AWS_SSH_KEY_USER]) {
                        buildlib.with_virtualenv('env') {

                            // get the ami-id to use
                            def ami_id = ""
                            if (!BASE_AMI_ID.isEmpty()){
                                ami_id = BASE_AMI_ID
                            } else {
                                def tag_args = build_aws_tag_args(AMI_SEARCH_TAGS)
                                ami_id = sh(returnStdout: true, script: "./oo-ec2-find-ami.py --region=${AWS_REGION} ${tag_args}").trim()
                            }

                            write_ansible_var_file(build_date, ami_id, jenkins_oreg_auth_user, jenkins_oreg_auth_password)

                            def ansible_arg_aws_accounts = convert_aws_account_property_to_ansible_arg('cli_aws_share_accounts', AMI_SHARE_ACCOUNTS)
                            timeout(120) {
                                ansiColor('xterm') {
                                    sh 'ansible-playbook openshift-ansible/playbooks/aws/openshift-cluster/build_ami.yml -e @provisioning_vars.yml -vvv'
                                    sh "ansible-playbook -e cli_ami_name='aos-${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE.split('.git')[0]}-${build_date}' -e g_play_current_region=${AWS_REGION} ${ansible_arg_aws_accounts} copy_ami_to_regions.yml"
                                }
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

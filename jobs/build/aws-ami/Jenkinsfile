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
openshift_aws_instance_type: m5.xlarge
openshift_aws_base_ami_name: ${BASE_AMI_NAME}
openshift_use_crio: ${USE_CRIO}
openshift_crio_use_rpm: True
# openshift_crio_systemcontainer_image_override is not needed when using the RPM
openshift_crio_systemcontainer_image_override: "${CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE}"
openshift_additional_repos:
- name: openshift-repo
  id: openshift-repo
  baseurl: ${env.YUM_BASE_URL}
  enabled: yes
  gpgcheck: 0
  sslverify: no
  sslclientcert: /var/lib/yum/client-cert.pem
  sslclientkey: /var/lib/yum/client-key.pem
  gpgkey: 'https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-release https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-beta https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-openshifthosted'
- name: fastdata
  description: 'Fastdata provides the official builds of OVS OpenShift supports'
  baseurl: 'https://mirror.ops.rhcloud.com/enterprise/rhel/rhel-7-fast-datapath-rpms/'
  file: 'fastdata-ovs'
  sslverify: False
  sslclientkey: /var/lib/yum/client-key.pem
  sslclientcert: /var/lib/yum/client-cert.pem
  enabled: True
  gpgkey: 'https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-release https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-beta https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-redhat-openshifthosted'
  gpgcheck: False
- name: ops-rpm
  file: ops-rpm
  state: present
  description: "Ops RPM Repo - Prod"
  baseurl: 'https://mirror.ops.rhcloud.com/libra/ops-rpm-7/\$basearch/'
  enabled: yes
  gpgcheck: yes
  sslverify: no
  sslclientcert: "/var/lib/yum/client-cert.pem"
  sslclientkey: "/var/lib/yum/client-key.pem"
  gpgkey: "https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-openshift-ops-2014,https://mirror.ops.rhcloud.com/libra/keys/RPM-GPG-KEY-openshift-ops-2017"
oreg_url: 'registry.reg-aws.openshift.com:443/openshift3/ose-\${component}:\${version}'
container_runtime_docker_storage_type: overlay2
container_runtime_docker_storage_setup_device: nvme1n1
docker_storage_path: /var/lib/containers
docker_storage_size: 200G
openshift_docker_options: '--log-driver=json-file --log-opt max-size=50m'
openshift_aws_node_group_config_node_volumes:
- device_name: /dev/sda1
  volume_size: 50
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
  openshift_short_version: "${OPENSHIFT_VERSION.tokenize(".")[0..1].join('.')}"
  openshift_release: "${OPENSHIFT_RELEASE}"
  openshift_version_release: "${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE}"
  build_date: "${build_date}"
  base_ami: "false"
openshift_aws_ami_name: "aos-${OPENSHIFT_VERSION}-${OPENSHIFT_RELEASE.split('.git')[0]}-${build_date}"
oreg_auth_user: ${jenkins_oreg_auth_user}
oreg_auth_password: ${jenkins_oreg_auth_password}
openshift_aws_ami_set_gquota_on_slash: false
openshift_aws_copy_base_ami_tags: True
openshift_node_image_prep_packages:
- python-docker
- rootlog
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
            parameterDefinitions: [
                [
                    name: 'TARGET_NODE',
                    description: 'Jenkins agent node',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'openshift-build-1'
                ],
                [
                    name: 'MAIL_LIST_SUCCESS',
                    description: 'Success Mailing List',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'aos-cicd@redhat.com'
                ],
                [
                    name: 'MAIL_LIST_FAILURE',
                    $class: 'hudson.model.StringParameterDefinition',
                    description: 'Failure Mailing List',
                    defaultValue: [
                        'tbielawa@redhat.com',
                        'jupierce@redhat.com',
                        'mwoodson@redhat.com',
                    ].join(',')
                ],
                [
                    name: 'FORCE_REBUILD',
                    description: 'Force rebuild even if no changes are detected?',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: false
                ],
                [
                    name: 'OPENSHIFT_VERSION',
                    description: 'Openshift Version (matches version in branch name for release builds)',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: '3.9.0'
                ],
                [
                    name: 'OPENSHIFT_RELEASE',
                    description: 'Release version (The release version number)',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: '0.0.0.git.0.1234567.el7'
                ],
                [
                    name: 'DEPLOYMENT_TYPE',
                    description: """origin - Openshift origin
openshift-enterprise - Openshift Enterprise online""",
                    $class: 'hudson.model.ChoiceParameterDefinition',
                    choices: "openshift-enterprise\norigin",
                    defaultValue: 'openshift-enterprise'
                ],
                [
                    name: 'YUM_BASE_URL',
                    description: 'Base url for repository.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'https://mirror.openshift.com/enterprise/online-int/latest/x86_64/os/'
                ],
                [
                    name: 'USE_CRIO',
                    description: 'Enable CRIO in Openshift for the AMI build.',
                    $class: 'hudson.model.BooleanParameterDefinition',
                    defaultValue: true
                ],
                [
                    name: 'CRIO_SYSTEM_CONTAINER_IMAGE_OVERRIDE',
                    description: 'CRIO system container override image.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'docker.io/runcom/cri-o-system-container:v3.8'
                ],
                [
                    name: 'OPENSHIFT_ANSIBLE_REPO_URL',
                    description: 'openshift-ansible repo URL.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'https://github.com/openshift/openshift-ansible.git'
                ],
                [
                    name: 'OPENSHIFT_ANSIBLE_CHECKOUT',
                    description: 'openshift-ansible checkout reference. Leave blank to use corresponding OCP release branch.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: ''
                ],

                // Parameters to search for AMI to use
                [
                    name: 'AMI_SEARCH_TAGS',
                    description: """Comma delimited tags (K=V) to use to find the base AMI to use
NOTE: This option is overridden by specifying the BASE_AMI_ID
NOTE: "base_ami=true" is probably necessary; otherwise a previous built ami
  will be used, and no packages will be updated!""",
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        'operating_system=RedHat',
                        'standard=true',
                        'base_ami=true'
                    ].join(',')
                ],
                [
                    name: 'BASE_AMI_ID',
                    description: """Base AMI id to build from.
NOTE: By default this job searches for the latest AMI based on AMI Search Tags.
If the AMI ID is specfied, it will override the search tags provided""",
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: ''
                ],

                [
                    name: 'AMI_SHARE_ACCOUNTS',
                    description: """Comma delimited list of AWS accounts to share the image with.
NOTE: Currently this only shares the AMI in the AWS_REGION defined.
531415883065 - Openshift DevEnv AWS Account
704252977135 - free-int AWS Account
639866565627 - Ops Test AWS Account
925374498059 - Perf Testing Account""",
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: [
                        '531415883065',
                        '704252977135',
                        '639866565627',
                        '925374498059'
                    ].join(',')
                ],

                // AWS Settings, these probably shouldn't change too often
                [
                    name: 'AWS_REGION',
                    description: 'AWS Region to use',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'us-east-1'
                ],
                [
                    name: 'BASE_AMI_NAME',
                    description: 'Base AMI instance name.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'cicd_openshift_node_ami_build'
                ],
                [
                    name: 'AWS_SSH_KEY_USER',
                    description: 'Name of the AWS SSH key user to use.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'ami_builder_key'
                ],
                [
                    name: 'VPC_NAME',
                    description: 'Specify a name that will be used for the VPC. Also used for VPC and other settings',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'cicd_build'
                ],
                [
                    name: 'AZ_NAME',
                    description: 'Specify an availability zone for the AMI build instance to use.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'us-east-1c'
                ],
                [
                    name: 'SG_NAME',
                    description: 'Specify a security group name for the AMI build instance to use.',
                    $class: 'hudson.model.StringParameterDefinition',
                    defaultValue: 'default'
                ],

                // Mock
                [
                    name: 'MOCK',
                    description: 'Mock run to pickup new Jenkins parameters?.',
                    $class: 'BooleanParameterDefinition',
                    defaultValue: false
                ],
            ]
        ]
    ]
)

if ( MOCK.toBoolean() ) {
    error( "Ran in mock mode to pick up any new parameters" )
}

if ( OPENSHIFT_ANSIBLE_CHECKOUT == "" ) {
    OCP_MAJOR = OPENSHIFT_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y.Z
    OCP_MINOR = OPENSHIFT_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y.Z
    OPENSHIFT_ANSIBLE_CHECKOUT = "release-${OCP_MAJOR}.${OCP_MINOR}"
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
env/bin/pip install --upgrade 'ansible==2.6.2' boto boto3
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
                from: 'aos-cicd@redhat.com',
                subject: "Error building aws ami",
                body: """Encoutered an error while running build_ami.yml: ${err}


Jenkins job: ${env.BUILD_URL}
""");
        // Re-throw the error in order to fail the job
        throw err
    }
}

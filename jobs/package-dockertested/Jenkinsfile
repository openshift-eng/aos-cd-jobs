def latestVersion(rpm, repo) {
    sh "sudo yum --disablerepo='*' --enablerepo='${repo}' makecache"
    sh(script: "sudo yum --disablerepo='*' --enablerepo='${repo}' --quiet list upgrades '${rpm}' | tail -n 1 | awk '{ print \$2 }'", returnStdout: true).trim()
}
def installedNVR(rpm) {
    sh(script: "ssh -F ${ssh_config} openshiftdevel 'rpm --query ${rpm} --queryformat %{NAME}-%{VERSION}-%{RELEASE}'", returnStdout: true).trim()
}
def runScript(script) {
    sh "scp -F ${ssh_config} ${script} openshiftdevel:/tmp/${script}"
    sh "ssh -F ${ssh_config} -t openshiftdevel \"bash -l -c /tmp/${script}\""
}
node('openshift-build-1') {
	properties ([[
		$class: 'ParametersDefinitionProperty',
		parameterDefinitions: [[
			$class: 'BooleanParameterDefinition',
			defaultValue: false,
			description: 'Destroy the previous <code>virtualenv</code> and install the <code>origin-ci-tool</code> from scratch.',
			name: 'CLEAN_INSTALL'
		]]
	],[
		$class: 'PipelineTriggersJobProperty',
		triggers: [[
			$class: 'TimerTrigger',
			spec: 'H H/3 * * *'
		]]
	],[
		$class: 'DisableConcurrentBuildsJobProperty',
	]])
	// https://issues.jenkins-ci.org/browse/JENKINS-33511
	env.WORKSPACE = pwd()
	stage ('Check to see if we need to run') {
	    next_docker = latestVersion('docker', 'rhel7next*')
	    next_cselinux = latestVersion('container-selinux', 'rhel7next*')
	    next_cstorage = latestVersion('container-storage-setup', 'rhel7next*')
	    next_skopeo = latestVersion('skopeo', 'rhel7next*')
	    next_atomic = latestVersion('atomic', 'rhel7next*')
	    echo "rhel7next: docker-${next_docker} container-selinux-${next_cselinux} container-storage-setup-${next_cstorage} skopeo-${next_skopeo} atomic-${next_atomic}"
	    test_docker = latestVersion('docker', 'dockertested')
	    test_cselinux = latestVersion('container-selinux', 'dockertested')
	    test_cstorage = latestVersion('container-storage-setup', 'dockertested')
	    test_skopeo = latestVersion('skopeo', 'dockertested')
	    test_atomic = latestVersion('atomic', 'dockertested')
	    echo "dockertested: docker-${test_docker} container-selinux-${test_cselinux} container-storage-setup-${test_cstorage} skopeo-${test_skopeo} atomic-${test_atomic}"
	    if ( next_docker == test_docker && next_cselinux == test_cselinux && next_cstorage == test_cstorage && next_skopeo == test_skopeo && next_atomic == test_atomic) {
	        echo 'No new packages. Aborting build.'
	        currentBuild.result = 'SUCCESS'
	    }
	}
	if ( currentBuild.result == 'SUCCESS' ) {
	    return
	}
	venv_dir = "${env.WORKSPACE}/origin-ci-tool"
	stage ('Create a virtualenv for the origin-ci-tool') {
		if ( CLEAN_INSTALL.toBoolean() ) {
			sh "rm -rf ${venv_dir}"
			sh "rm -rf ${env.WORKSPACE}/.config"
			sh "virtualenv ${venv_dir} --system-site-packages"
		}
		sh "test -d ${venv_dir}"
	}
	stage ('Fetch the scripts') {
	    checkout scm
	}
	withEnv([
		"VIRTUAL_ENV=${venv_dir}",
		"PATH=${venv_dir}/bin:${env.PATH}",
		"PYTHON_HOME=",
		"OCT_CONFIG_HOME=${env.WORKSPACE}/.config",
		"ANSIBLE_SSH_CONTROL_PATH_DIR=${env.HOME}/.ansible/cp",
		"ANSIBLE_SSH_CONTROL_PATH=%(directory)s/%%h-%%p-%%r"
	]) {
		stage ('Install dependencies in the virtualenv') {
			sh "pip install --ignore-installed --upgrade pip"
			sh 'pip install --ignore-installed boto boto3'
		}
		stage ('Install the origin-ci-tool') {
			sh 'pip install git+https://github.com/openshift/origin-ci-tool.git --process-dependency-links'
		}
		stage ('Configure the origin-ci-tool') {
			sh 'oct configure ansible-client verbosity 2'
			sh 'oct configure aws-client keypair_name libra'
			sh "oct configure aws-client private_key_path /home/jenkins/.ssh/devenv.pem"
		}
		try {
			stage ('Provision the remote host') {
				sh "oct provision remote all-in-one --os rhel --stage bare --provider aws --name package-dockertest-${env.BUILD_NUMBER} --discrete-ssh-config"
				ssh_config = "${env.OCT_CONFIG_HOME}/origin-ci-tool/inventory/.ssh_config"
			}
			stage ('Install CI user') {
				sh 'oct prepare user'
				sh "sed -i 's/User ec2-user/User origin/g' ./.config/origin-ci-tool/inventory/.ssh_config"
			}
			stage ('Configure TMPFS') {
				runScript './configure-tmpfs.sh'
			}
			stage ('Install distribution dependencies') {
				sh 'oct prepare dependencies'
			}
			stage ('Install Golang') {
				sh 'oct prepare golang --version 1.7.5 --repourl https://cbs.centos.org/repos/paas7-openshift-origin36-candidate/x86_64/os/'
			}
			stage ('Install Docker') {
				sh 'oct prepare docker --repo "rhel7next*"'
			}
			stage ('Install Other RHEL7Next Dependencies') {
				runScript './install-rhel7next-dependencies.sh'
				docker_rpm = installedNVR('docker')
				container_selinux_rpm = installedNVR('container-selinux')
				container_storage_setup_rpm = installedNVR('container-storage-setup')
				skopeo_rpm = installedNVR('skopeo')
				atomic_rpm = installedNVR('atomic')
				echo "Installed: ${docker_rpm} ${container_selinux_rpm} ${container_storage_setup_rpm} ${skopeo_rpm} ${atomic_rpm}"
			}
			stage ('Prepare source repositories') {
				sh 'oct prepare repositories'
			}
			stage ('Build an Origin release') {
				runScript './build-origin-release.sh'
			}
			stage ('Build an OpenShift Ansible release') {
				runScript './build-openshift-ansible-release.sh'
			}
			stage ('Install the OpenShift Ansible release') {
				runScript './install-openshift-ansible-release.sh'
			}
			stage ('Install the Ansible plugins') {
				runScript './install-ansible-plugins.sh'
			}
			stage ('Install the Origin release') {
				runScript './install-origin-release.sh'
            }
			stage ('Run the extended conformance suite') {
				runScript './run-origin-tests.sh'
			}
		} catch (Exception err) {
			currentBuild.result = 'FAILURE'
		} finally {
			stage ('Deprovision the remote host') {
				sh 'oct deprovision'
			}
			if ( currentBuild.result != 'FAILURE' ) {
				stage ('Update the state of the dockertested repo') {
					sh 'kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM'
					sh "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com /mnt/rcm-guest/puddles/RHAOS/scripts/update-dockertested-repo.sh ${docker_rpm} ${container_selinux_rpm} ${container_storage_setup_rpm} ${skopeo_rpm} ${atomic_rpm}"
				}
				stage ('Send out an e-mail about new versions') {
					mail (
						to: 'aos-devel@redhat.com',
						cc: 'skuznets@redhat.com',
						subject: "${docker_rpm} and dependencies pushed to dockertested repository",
						body: """The latest job[1] marked the following RPMs as successful:
${docker_rpm}
${container_selinux_rpm}
${container_storage_setup_rpm}
${skopeo_rpm}
${atomic_rpm}

These RPMs have been pushed to the dockertested[2] repository.

[1] ${env.JOB_URL}${env.BUILD_NUMBER}
[2] https://mirror.openshift.com/enterprise/rhel/dockertested/x86_64/os/"""
					)
				}
			}
		}
	}
}

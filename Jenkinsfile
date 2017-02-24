node('buildvm-devops') {
	properties ([[
		$class: 'ParametersDefinitionProperty',
		parameterDefinitions: [[
			$class: 'BooleanParameterDefinition',
			defaultValue: false,
			description: 'Destroy the previous <code>virtualenv</code> and install the <code>origin-ci-tool</code> from scratch.',
			name: 'CLEAN_INSTALL'
		]]
	]])
	// https://issues.jenkins-ci.org/browse/JENKINS-33511
	env.WORKSPACE = pwd()
	venv_dir = "${env.WORKSPACE}/origin-ci-tool"
	stage ('Create a virtualenv for the origin-ci-tool') {
		if ( params.CLEAN_INSTALL ) {
			sh "rm -rf ${venv_dir}"
			sh "virtualenv ${venv_dir} --system-site-packages"
		}
		sh "test -d ${venv_dir}"
	}
	withEnv([
		"VIRTUAL_ENV=${venv_dir}",
		"PATH=${venv_dir}/bin:${env.PATH}",
		"PYTHON_HOME=",
		"OCT_CONFIG_HOME=${env.WORKSPACE}/.config"
	]) {
		stage ('Install dependencies in the virtualenv') {
			sh "pip install --upgrade pip"
			sh 'pip install boto boto3'
		}
		stage ('Install the origin-ci-tool') {
			sh 'pip install git+https://github.com/openshift/origin-ci-tool.git --process-dependency-links'
		}
		stage ('Configure the origin-ci-tool') {
			sh 'oct configure ansible-client verbosity 2'
			sh 'oct configure aws-client keypair_name libra'
			withCredentials([[$class: 'FileBinding', credentialsId: 'devenv', variable: 'PRIVATE_KEY_PATH']]) {
				sh "oct configure aws-client private_key_path ${env.PRIVATE_KEY_PATH}"
			}
		}
		try {
			withCredentials([[$class: 'FileBinding', credentialsId: 'aws', variable: 'AWS_CONFIG_FILE']]) {
				stage ('Provision the remote host') {
					sh "oct provision remote all-in-one --os rhel --stage bare --provider aws --name ${env.JOB_NAME}-${env.BUILD_NUMBER} --discrete-ssh-config"
					def ssh_config = "${env.OCT_CONFIG_HOME}/origin-ci-tool/inventory/.ssh_config"
				}
				stage ('Install distribution dependencies') {
					sh 'oct prepare dependencies'
				}
				stage ('Install Golang') {
					sh 'oct prepare golang --version 1.6.3 --repo oso-rhui-rhel-server-releases-optional'
				}
				stage ('Install Docker') {
					sh 'oct prepare docker --repourl https://mirror.openshift.com/enterprise/rhel/rhel7next/extras/'
					docker_rpm = sh script: 'rpm --query docker --queryformat %{SOURCERPM}', returnStdout: true
					container_selinux_rpm = sh script: 'rpm --query container-selinux --queryformat %{SOURCERPM}', returnStdout: true
				}
				stage ('Prepare source repositories') {
					sh 'oct prepare repositories'
				}
				stage ('Build an Origin release') {
					sh "ssh -F ${ssh_config} openshiftdevel 'cd /data/src/github/openshift/origin; sudo su origin; hack/build-base-images.sh; make release'"
				}
				stage ('Run the extended conformance suite') {
					sh "ssh -F ${ssh_config} openshiftdevel 'cd /data/src/github/openshift/origin; sudo su origin; make test-extended SUITE=conformance'"
				}
			}
		} finally {
			stage ('Deprovision the remote host') {
				sh 'oct deprovision'
			}
			if ( currentBuild.result == 'SUCCESS' ) {
				stage ('Update the state of the dockertested repo') {
					sh 'kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM'
					sh "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com /mnt/rcm-guest/puddles/RHAOS/scripts/update-dockertested-repo.sh ${docker_rpm} ${container_selinux_rpm}"
				}
				stage ('Send out an e-mail about new versions') {
					mail (
						to: ['aos-devel@redhat.com', 'skuznets@redhat.com'],
						subject: "${docker_rpm} and ${container_selinux_rpm} pushed to dockertested repository",
						body: """The latest job[1] marked the following RPMs as successful:
${docker_rpm}
${container_selinux_rpm}

These RPMs have been pushed to the dockertested[2] repository.

[1] ${env.JOB_URL}
[2] https://mirror.openshift.com/enterprise/rhel/dockertested/x86_64/os/"""
					)
				}
			}
		}
	}
}
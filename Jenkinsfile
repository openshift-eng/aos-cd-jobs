node('buildvm-devops') {
	stage ('Create a virtualenv for the origin-ci-tool') {
		def venv_dir = "${env.WORKSPACE}/origin-ci-tool"
		sh "test -d ${venv_dir} || virtualenv ${venv_dir} --system-site-packages"
	}
	environment {
		VIRTUAL_ENV = "${venv_dir}"
		PATH = "${venv_dir}/bin:${env.PATH}"
		PYTHON_HOME = ""
		OCT_CONFIG_HOME = "${env.WORKSPACE}/.config"
	}
	stage ('Install and configure the origin-ci-tool') {
		sh 'pip install boto boto3'
		sh 'pip install git+https://github.com/openshift/origin-ci-tool.git --process-dependency-links'
		sh 'oct configure ansible-client verbosity 2'
		sh 'oct configure aws-client keypair_name libra'
		withCredentials([file(credentialsId: 'devenv', variable: 'PRIVATE_KEY_PATH')]) {
			sh "oct configure aws-client private_key_path ${env.PRIVATE_KEY_PATH}"
		}
	}
	try {
		withCredentials([file(credentialsId: 'aws', variable: 'AWS_CONFIG_FILE')]) {
			stage ('Provision the remote host') {
				sh "oct provision remote all-in-one --os rhel --stage bare --provider aws --name ${env.JOB_NAME}-${env.BUILD_NUMBER} --discrete-ssh-config"
				def ssh_config = "${env.OCT_CONFIG_HOME}/origin-ci-tool/inventory/.ssh_config"
			}
			stage ('Prepare the remote host for testing') {
				sh 'oct prepare dependencies'
				sh 'oct prepare golang --version 1.6.3 --repo oso-rhui-rhel-server-releases-optional'
				sh 'oct prepare docker --repourl https://mirror.openshift.com/enterprise/rhel/rhel7next/extras/'
				def docker_version = sh script: 'rpm --query docker --queryformat %{VERSION}', returnStdout: true
				def container_selinux_version = sh script: 'rpm --query container-selinux --queryformat %{VERSION}', returnStdout: true
				sh 'oct prepare repositories'
			}
			stage ('Run the extended conformance suite') {
				sh "ssh -F ${ssh_config} openshiftdevel 'cd /data/src/github/openshift/origin; sudo su origin; hack/build-base-images.sh; make release'"
				sh "ssh -F ${ssh_config} openshiftdevel 'cd /data/src/github/openshift/origin; sudo su origin; make test-extended SUITE=conformance'"
			}
		}
	} finally {
		sh 'oct deprovision'
		when { currentBuild.result == 'SUCCESS' }
		sh 'kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM'
		sh "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com /mnt/rcm-guest/puddles/RHAOS/scripts/update-dockertested-repo.sh ${docker_version} ${container_selinux_version}"
		mail (
			to: ['aos-devel@redhat.com', 'skuznets@redhat.com'],
			subject: "docker-${docker_version} and container-selinux-${container_selinux_version} pushed to dockertested repository",
			body: """The latest job[1] marked the following RPMs as successful:
docker-${docker_version}
container-selinux-${container_selinux_version}

These RPMs have been pushed to the dockertested[2] repository.

[1] ${env.JOB_URL}
[2] https://mirror.openshift.com/enterprise/rhel/dockertested/x86_64/os/"""
		)
	}
}
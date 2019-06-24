def latestVersion(rpm, repo) {
    sh "sudo yum --disablerepo='*' --enablerepo='${repo}' --quiet makecache"
    sh(script: "sudo yum --disablerepo='*' --enablerepo='${repo}' --quiet list upgrades '${rpm}' | tail -n 1 | awk '{ print \$2 }'", returnStdout: true).trim()
}
def installedNVR(rpm) {
    sh(script: "ssh -F ${ssh_config} openshiftdevel 'rpm --query ${rpm} --queryformat %{NAME}-%{VERSION}-%{RELEASE}'", returnStdout: true).trim()
}
def runScript(script, args=[]) {
    sh "scp -F ${ssh_config} ${script} openshiftdevel:/tmp/${script}"
    sh "ssh -F ${ssh_config} -t openshiftdevel \"bash -l -c '/tmp/${script} ${args.join(' ')}'\""
}
node('openshift-build-1') {
	properties ([
	    [
		$class: 'DisableConcurrentBuildsJobProperty',
	    ]
	])
	// https://issues.jenkins-ci.org/browse/JENKINS-33511
	env.WORKSPACE = pwd()
	def packages = ['docker', 'container-selinux', 'container-storage-setup', 'skopeo', 'atomic', 'python-pytoml', 'oci-register-machine', 'oci-umount']
	def installed_packages = []

	stage ('Check to see if we need to run') {
		def versions = []
		for(int i = 0; i < packages.size(); ++i) {
			def pkg = packages[i]
			def package_versions = [:]
			package_versions['next'] = latestVersion(pkg, 'rhel7next*')
			package_versions['current'] = latestVersion(pkg, 'dockertested')
			versions.add([pkg,package_versions])
		}

		def sync_necessary = false
		def table = "Package\tCurrent\tRHEL 7 Next\n"
		for(int i = 0; i < versions.size(); ++i) {
			def pkg = versions[i][0]
			def package_version = versions[i][1]
			table = table + "${pkg}\t${package_version['current']}\t${package_version['next']}\n"
			if (package_version['current'] != package_version['next']) {
				sync_necessary = true
			}
		}
		echo table

		if (! sync_necessary) {
			currentBuild.result = 'SUCCESS'
	        echo 'No new packages. Aborting build.'
		}
	}
	if ( currentBuild.result == 'SUCCESS' ) {
	    return
	}
	venv_dir = "${env.WORKSPACE}/origin-ci-tool"
	stage ('Create a virtualenv for the origin-ci-tool') {
		sh "rm -rf ${venv_dir}"
		sh "rm -rf ${env.WORKSPACE}/.config"
		sh "virtualenv ${venv_dir} --system-site-packages"
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
		stage ('Debug variables') {
			echo "${env.VIRTUAL_ENV}"
			echo "${env.PATH}"
			echo "${env.PYTHON_HOME}"
			echo "${env.OCT_CONFIG_HOME}"
			echo "${env.ANSIBLE_SSH_CONTROL_PATH_DIR}"
			echo "${env.ANSIBLE_SSH_CONTROL_PATH}"
			sh "which python"
			sh "which python2"
			sh "which pip"
			sh "pip --version"
		}
		stage ('Install dependencies in the virtualenv') {
			sh "python -m pip install --ignore-installed --upgrade pip"
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
			stage ('Install the RHEL7Next repositories') {
				sh "scp -F ${ssh_config} ./rhel7next.repo openshiftdevel:/tmp/rhel7next.repo"
				sh "ssh -F ${ssh_config} openshiftdevel \"sudo mv /tmp/rhel7next.repo /etc/yum.repos.d/\""
			}
			stage ('Install distribution dependencies') {
				sh 'oct prepare dependencies'
			}
			stage ('Install Golang') {
				sh 'oct prepare golang --version 1.8.3 --repourl https://cbs.centos.org/repos/paas7-openshift-origin37-candidate/x86_64/os/'
			}
			stage ('Install Docker') {
				sh 'oct prepare docker --repo "rhel7next*"'
			}
			stage ('Install Other RHEL7Next Dependencies') {
				runScript "./install-rhel7next-dependencies.sh", packages
				def table = "Installed\n"
				for(int i = 0; i < packages.size(); ++i) {
					def pkg = packages[i]
					def installed_package = installedNVR(pkg)
					table = table + "${installed_package}\n"
					installed_packages.add(installed_package)
				}
				echo table
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
					sh 'kinit -k -t /home/jenkins/ocp-build-buildvm.openshift.eng.bos.redhat.com.keytab ocp-build/buildvm.openshift.eng.bos.redhat.com@REDHAT.COM'
					sh "ssh ocp-build@rcm-guest.app.eng.bos.redhat.com /mnt/rcm-guest/puddles/RHAOS/scripts/update-dockertested-repo.sh ${installed_packages.join(' ')}"
				}
				stage ('Send out an e-mail about new versions') {
					mail (
						to: 'aos-cicd@redhat.com',
						cc: 'skuznets@redhat.com',
						subject: "${installed_packages[0]} and dependencies pushed to dockertested repository",
						body: """The latest job[1] marked the following RPMs as successful:
${installed_packages.join('\n')}

These RPMs have been pushed to the dockertested[2] repository.

[1] ${env.JOB_URL}${env.BUILD_NUMBER}
[2] https://mirror.openshift.com/enterprise/rhel/dockertested/x86_64/os/"""
					)
				}
			}
		}
	}
}

node('buildvm-devops') {
	stages {
		stage ('Create a virtualenv for the origin-ci-tool') {
			steps {
				sh 'virtualenv origin-ci-tool --system-site-packages'
			}
		}
		withEnv([
			'VIRTUAL_ENV=${WORKSPACE}/origin-ci-tool',
			'PATH=${WORKSPACE}/origin-ci-tool/bin:${PATH}',
			'PYTHON_HOME=',
			'OCT_CONFIG_HOME=${WORKSPACE}/.config'
		]) {
			stage ('Install and configure the origin-ci-tool') {
				steps {
					sh 'pip install boto boto3'
					sh 'pip install git+https://github.com/openshift/origin-ci-tool.git --process-dependency-links'
					sh 'oct configure ansible-client verbosity 2'
					sh 'oct configure aws-client keypair_name libra'
					withCredentials([file(credentialsId: 'devenv', variable: 'PRIVATE_KEY_PATH')]) {
						sh 'oct configure aws-client private_key_path ${PRIVATE_KEY_PATH}'
					}
				}
			}
			withCredentials([file(credentialsId: 'aws', variable: 'AWS_CONFIG_FILE')]) {
				stage ('Provision the remote host') {
					steps {
						sh 'oct provision remote all-in-one --os rhel --stage bare --provider aws --name ${JOB_NAME}-${BUILD_NUMBER} --discrete-ssh-config'
					}
				}
				try {
					stage ('Prepare the remote host for testing') {
						steps {
							sh 'oct prepare dependencies'
							sh 'oct prepare golang --version 1.6.3 --repo oso-rhui-rhel-server-releases-optional'
							sh 'oct prepare docker --repourl https://mirror.openshift.com/enterprise/rhel/rhel7next/extras/'
							sh 'oct prepare repositories'
						}
					}
					stage ('Run the extended conformance suite') {
						steps {
							sh 'ssh -F ${OCT_CONFIG_HOME}/origin-ci-tool/inventory/.ssh_config openshiftdevel "cd /data/src/github/openshift/origin; sudo su origin; hack/build-base-images.sh; make release"'
							sh 'ssh -F ${OCT_CONFIG_HOME}/origin-ci-tool/inventory/.ssh_config openshiftdevel "cd /data/src/github/openshift/origin; sudo su origin; make test-extended SUITE=conformance"'
						}
					}
				} catch(err) {
					sh 'oct deprovision'
					throw err
				}
			}
			stage ('Trigger sync to dockertested repository') {
				steps {
					sh 'kinit -k -t /home/jenkins/ocp-build.keytab ocp-build/atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com@REDHAT.COM'
					sh 'ssh ocp-build@rcm-guest.app.eng.bos.redhat.com /mnt/rcm-guest/puddles/RHAOS/scripts/update-dockertested-repo.sh'
				}
			}
		}
	}
}
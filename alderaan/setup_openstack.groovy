#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
println "Current pipeline job build id is '${pipeline_id}'"
def node_label = 'CCI && ansible-2.4'
def install_openstack = OPENSTACK_INSTALL.toString().toUpperCase()

// install openstack
stage ('openstack_install') {
	if (install_openstack) {
		currentBuild.result = "SUCCESS"
		node('CCI && US') {
			// get properties file
			if (fileExists("openstack.properties")) {
				println "Looks like openstack.properties file already exists, erasing it"
				sh "rm openstack.properties"
			}
			// get properties file
			//sh  "wget http://file.rdu.redhat.com/~nelluri/pipeline/openstack.properties"
			sh "wget ${OPENSTACK_PROPERTY_FILE} -O openstack.properties"
			sh "cat openstack.properties"
			def openstack_properties = readProperties file: "openstack.properties"
			def rhos_release_url = openstack_properties['RHOS_RELEASE_URL']
			//def rhel_base_url = openstack_properties['RHEL_7_SERVER_BETA_BASE_URL']
			def stack_passwd = openstack_properties['STACK_PASSWORD']
			def external_ip = openstack_properties['EXTERNAL_NETWORK_VIP']
			def private_external_ip = openstack_properties['PRIVATE_EXTERNAL_ADDRESS']
			def dns_server = openstack_properties['DNS_SERVER']
			def instack_json = openstack_properties['INSTACKENV_JSON']
			def cloud_title = openstack_properties['CLOUD_TITLE']
			def ticket = openstack_properties['TICKET_NUMBER']
			def foreman_url = openstack_properties['FOREMAN_URL']
			def undercloud = openstack_properties['UNDERCLOUD_HOSTNAME']
			//def template_repo = openstack_properties['TEMPLATE_REPOSITORY']
			def ansible_passwd = openstack_properties['ANSIBLE_SSH_PASS']
			//def passthrough_host = openstack_properties['PASSTHROUGH_HOSTNAME']
			def ntp_server = openstack_properties['NTP_SERVER']
			//def es = openstack_properties['ES']
			def cloud_name = openstack_properties['CLOUD_NAME']
			def graphite = openstack_properties['GRAPHITE']
			def jenkins_slave_label = openstack_properties['JENKINS_SLAVE_LABEL']
			def num_compute = openstack_properties['NUM_COMPUTE']
			def num_storage = openstack_properties['NUM_STORAGE']
	                def access_token = openstack_properties['PERSONAL_ACCESS_TOKEN']
			def extra_vars = openstack_properties['EXTRA_VARS']
			//def private_lan = openstack_properties['DEPLOY_EXTERNAL_PRIVATE_LAN']
			//def private_nat = openstack_properties['DEPLOY_EXTERNAL_PRIVATE_NAT']
                        
			// debug info
                        println "----------USER DEFINED OPTIONS-------------------"
                        println "-------------------------------------------------"
                        println "-------------------------------------------------"
                        println "RHOS_RELEASE_URL: '${rhos_release_url}'"
                        println "STACK_PASSWORD: '${stack_passwd}'"
                        println "EXTERNAL_NETWORK_VIP: '${external_ip}'"
                        println "DNS_SERVER: '${dns_server}'"
			println "INSTACKENV_JSON: '${instack_json}'"
			println "TICKET_NUMBER: '${ticket}'"
			println "CLOUD_TITLE: '${cloud_title}'"
			println "FOREMAN_URL: '${foreman_url}'"
			println "UNDERCLOUD_HOSTNAME: '${undercloud}'"
			println "ANSIBLE_SSH_PASS: '${ansible_passwd}'"
			println "NTP_SERVER: '${ntp_server}'"
			println "CLOUD_NAME: '${cloud_name}'"
			println "GRAPHITE: '${graphite}'"
			println "JENKINS_SLAVE_LABEL: '${jenkins_slave_label}'"
                        println "-------------------------------------------------"
                        println "-------------------------------------------------"	
		
			// Run scale-ci openstack install
			try {
			    openstack_build = build job: 'scale-ci_install_OpenStack',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
					
						[$class: 'StringParameterValue', name: 'RHOS_RELEASE_URL', value: rhos_release_url ],
						[$class: 'StringParameterValue', name: 'STACK_PASSWORD', value: stack_passwd ],
						[$class: 'StringParameterValue', name: 'EXTERNAL_NETWORK_VIP', value: external_ip ],
						[$class: 'StringParameterValue', name: 'DNS_SERVER', value: dns_server ],
						[$class: 'StringParameterValue', name: 'INSTACKENV_JSON', value: instack_json ],
                                                [$class: 'StringParameterValue', name: 'TICKET_NUMBER', value: ticket ],
                                                [$class: 'StringParameterValue', name: 'CLOUD_TITLE', value: cloud_title ],
                                                [$class: 'StringParameterValue', name: 'FOREMAN_URL', value: foreman_url ],
                                                [$class: 'StringParameterValue', name: 'UNDERCLOUD_HOSTNAME', value: undercloud ],
                                                //[$class: 'StringParameterValue', name: 'TEMPLATE_REPOSITORY', value: template_repo ],
                                                [$class: 'StringParameterValue', name: 'ANSIBLE_SSH_PASS', value: ansible_passwd ],
                                                //[$class: 'StringParameterValue', name: 'PASSTHROUGH_HOSTNAME', value: passthrough_host ],
                                                [$class: 'StringParameterValue', name: 'NTP_SERVER', value: ntp_server ],
                                                //[$class: 'StringParameterValue', name: 'ES', value: es ],
                                                [$class: 'StringParameterValue', name: 'CLOUD_NAME', value: cloud_name ],
                                                [$class: 'StringParameterValue', name: 'GRAPHITE', value: graphite ],	
						[$class: 'StringParameterValue', name: 'NUM_COMPUTE', value: num_compute ],
						[$class: 'StringParameterValue', name: 'NUM_STORAGE', value: num_storage ],
						[$class: 'StringParameterValue', name: 'PRIVATE_EXTERNAL_ADDRESS', value: private_external_ip ],
					        [$class: 'StringParameterValue', name: 'EXTRA_VARS', value: extra_vars ],
						[$class: 'StringParameterValue', name: 'PERSONAL_ACCESS_TOKEN', value: access_token ],
                                                [$class: 'StringParameterValue', name: 'JENKINS_SLAVE_LABEL', value: jenkins_slave_label ]]
			} catch ( Exception e) {
                	echo "SCALE_CI_OPENSTACK_INSTALL Job failed with the following error: "
                	echo "${e.getMessage()}"
			mail(
                                to: 'nelluri@redhat.com',
                                subject: 'Scale-ci-install-openstack job failed',
                                body: """\
                                        Encoutered an error while running the scale-ci-install-openstack job: ${e.getMessage()}\n\n
                                        Jenkins job: ${env.BUILD_URL}
                        """)
                	currentBuild.result = "FAILURE"
			sh "exit 1"
            		}
                	println "SCALE-CI-OPENSTACK-INSTALL build ${openstack_build.getNumber()} completed successfully"
		}
	}
}

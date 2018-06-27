#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
println "Current pipeline job build id is '${pipeline_id}'"
def node_label = 'CCI && ansible-2.4'
def browbeat = BROWBEAT_INSTALL.toString().toUpperCase()

// run browbeat install
stage ('BROWBEAT') {
	if (browbeat == "TRUE") {
		currentBuild.result = "SUCCESS"
		node('CCI && US') {
			// get properties file
			if (fileExists("browbeat.properties")) {
				println "Looks like browbeat.properties file already exists, erasing it"
				sh "rm browbeat.properties"
			}
			// get properties file
			//sh "wget http://file.rdu.redhat.com/~nelluri/pipeline/browbeat.properties"
			sh "wget ${BROWBEAT_PROPERTY_FILE} -O browbeat.properties"
			sh "cat browbeat.properties"
			def browbeat_properties = readProperties file: "browbeat.properties"
			def openstack_server = browbeat_properties['OPENSTACK_SERVER']
			def user = browbeat_properties['OPENSTACK_USER']
			def graphite = browbeat_properties['GRAPHITE']
			def graphite_prefix = browbeat_properties['GRAPHITE_PREFIX']
			def access_token = browbeat_properties['PERSONAL_ACCESS_TOKEN']
			def dns_server = browbeat_properties['DNS_SERVER']
			def collectd_compute = browbeat_properties['BROWBEAT_COLLECTD_COMPUTE']
			def collectd_rabbitmq = browbeat_properties['BROWBEAT_COLLECTD_RABBITMQ']
			def collectd_ceph = browbeat_properties['BROWBEAT_COLLECTD_CEPH']

			// debug info
			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "OPENSTACK_SERVER: '${openstack_server}'"
			println "OPENSTACK_USER: '${user}'"
			println "GRAPHITE: '${graphite}'"
			println "GRAPHITE_PREFIX: '${graphite_prefix}'"
			println "-------------------------------------------------"
			println "-------------------------------------------------"

			// Run browbeat job
			try {
				browbeat_build = build job: 'scale-ci_install_Browbeat',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'OPENSTACK_SERVER', value: openstack_server ],
						[$class: 'StringParameterValue', name: 'OPENSTACK_USER', value: user ],
						[$class: 'StringParameterValue', name: 'GRAPHITE', value: graphite ],
						[$class: 'StringParameterValue', name: 'PERSONAL_ACCESS_TOKEN', value: access_token ],
						[$class: 'StringParameterValue', name: 'DNS_SERVER', value: dns_server ],
						[$class: 'StringParameterValue', name: 'BROWBEAT_COLLECTD_COMPUTE', value: collectd_compute ],
						[$class: 'StringParameterValue', name: 'BROWBEAT_COLLECTD_RABBITMQ', value: collectd_rabbitmq ],
						[$class: 'StringParameterValue', name: 'BROWBEAT_COLLECTD_CEPH', value: collectd_ceph ],
						[$class: 'StringParameterValue', name: 'GRAPHITE_PREFIX', value: graphite_prefix ]]
			} catch ( Exception e) {
				echo " Browbeat failed with the following error: "
				echo "${e.getMessage()}"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'Browbeat job failed',
					body: """\
						Encoutered an error while running the browbeat job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
				sh "exit 1"
			}
				println "Browbeat build ${browbeat_build.getNumber()} completed successfully"
		}
	}
}

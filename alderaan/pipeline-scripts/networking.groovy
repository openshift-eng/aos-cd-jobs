#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def networking = NETWORKING.toString().toUpperCase()
def property_file_name = "networking.properties"

println "Current pipeline job build id is '${pipeline_id}'"

stage (node_label) {
	if (networking == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the property file already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${NETWORKING_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			def networking_properties = readProperties file: property_file_name
			def jump_host = networking_properties['JUMP_HOST']
			def user = networking_properties['USER']
			def use_proxy = networking_properties['USE_PROXY']
			def proxy_user = networking_properties['PROXY_USER']
			def proxy_host = networking_properties['PROXY_HOST']
			def mode = networking_properties['MODE']
			def token = networking_properties['GITHUB_TOKEN']
			def repo = networking_properties['PERF_REPO']
			def server = networking_properties['PBENCH_SERVER']
			def setup_pbench = networking_properties['SKIP_REGISTER_PBENCH']
			def containerized = networking_properties['CONTAINERIZED']

			// copy the parameters file to jump host
			sh "git clone https://${token}@${repo} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
			sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${jump_host}:/root/properties"
	
			// Run networking job
			try {
				networking_build = build job: 'SVT_Network_Performance_Test',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'USER', value: user ],
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: token ],
						[$class: 'BooleanParameterValue', name: 'SKIP_REGISTER_PBENCH', value: Boolean.valueOf(setup_pbench) ],
						[$class: 'StringParameterValue', name: 'CONTAINERIZED', value: containerized ],
						[$class: 'StringParameterValue', name: 'MODE', value: mode ]]
			} catch ( Exception e) {
				echo "NETWORKING-TEST Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'Networking-test job failed',
					body: """\
						Encoutered an error while running the networking-scale-test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
 				sh "exit 1"
			}
			println "NETWORKING-TEST build ${networking_build.getNumber()} completed successfully"
		}
	}
}

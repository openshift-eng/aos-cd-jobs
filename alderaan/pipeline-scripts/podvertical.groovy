#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def podvertical = PODVERTICAL.toString().toUpperCase()
def property_file_name = "podvertical.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run podvertical scale test
stage ('podvertical_scale_test') {
	if (podvertical == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the propertyfile already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${PODVERTICAL_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			def podvertical_properties = readProperties file: property_file_name
			def jump_host = podvertical_properties['JUMP_HOST']
			def user = podvertical_properties['USER']
			def tooling_inventory_path = podvertical_properties['TOOLING_INVENTORY']
			def clear_results = podvertical_properties['CLEAR_RESULTS']
			def move_results = podvertical_properties['MOVE_RESULTS']
			def use_proxy = podvertical_properties['USE_PROXY']
			def setup_pbench = podvertical_properties['SETUP_PBENCH']
			def proxy_user = podvertical_properties['PROXY_USER']
			def proxy_host = podvertical_properties['PROXY_HOST']
			def containerized = podvertical_properties['CONTAINERIZED']
			def pods = podvertical_properties['PODS']
			def iterations = podvertical_properties['ITERATIONS']
			def token = podvertical_properties['GITHUB_TOKEN']
			def repo = podvertical_properties['PERF_REPO']
			def server = podvertical_properties['PBENCH_SERVER']
	
			// debug info
			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "JUMP_HOST: '${jump_host}'"
			println "USER: '${user}'"
			println "TOOLING_INVENTORY_PATH: '${tooling_inventory_path}'"
			println "CLEAR_RESULTS: '${clear_results}'"
			println "MOVE_RESULTS: '${move_results}'"
			println "USE_PROXY: '${use_proxy}'"
			println "PROXY_USER: '${proxy_user}'"
			println "PROXY_HOST: '${proxy_host}'"
			println "CONTAINERIZED: '${containerized}'"
			println "TOKEN: '${token}'"
			println "-------------------------------------------------"
			println "-------------------------------------------------"

			// copy the parameters file to jump host
			sh "git clone https://${token}@${repo} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
			sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${jump_host}:/root/properties"

			// Run podvertical job
			try {
				podvertical_build = build job: 'PODVERTICAL',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'USER', value: user ],
						[$class: 'StringParameterValue', name: 'TOOLING_INVENTORY', value: tooling_inventory_path ],
						[$class: 'BooleanParameterValue', name: 'CLEAR_RESULTS', value: Boolean.valueOf(clear_results) ],
						[$class: 'BooleanParameterValue', name: 'SETUP_PBENCH', value: Boolean.valueOf(setup_pbench) ],
						[$class: 'BooleanParameterValue', name: 'MOVE_RESULTS', value: Boolean.valueOf(move_results) ],
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'StringParameterValue', name: 'PODS', value: pods ],
						[$class: 'StringParameterValue', name: 'ITERATIONS', value: iterations ],
						[$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ],
						[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: token ]]
			} catch ( Exception e) {
				echo "PODVERTICAL Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'Podvertical-scale-test job failed',
					body: """\
						Encoutered an error while running the podvertical-scale-test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
                        	sh "exit 1"
                        }
                        println "POD-VERTICAL build ${podvertical_build.getNumber()} completed successfully"
		}
	}
}

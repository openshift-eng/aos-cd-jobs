#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def nodevertical = NODEVERTICAL_SCALE_TEST.toString().toUpperCase()
def property_file_name = "nodevertical.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run nodevertical scale test
stage ('nodevertical_scale_test') {
	if (nodevertical == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the property file already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${NODEVERTICAL_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			def nodevertical_properties = readProperties file: property_file_name
			def jump_host = nodevertical_properties['JUMP_HOST']
			def user = nodevertical_properties['USER']
			def tooling_inventory_path = nodevertical_properties['TOOLING_INVENTORY']
			def clear_results = nodevertical_properties['CLEAR_RESULTS']
			def move_results = nodevertical_properties['MOVE_RESULTS']
			def use_proxy = nodevertical_properties['USE_PROXY']
			def proxy_user = nodevertical_properties['PROXY_USER']
			def proxy_host = nodevertical_properties['PROXY_HOST']
			def containerized = nodevertical_properties['CONTAINERIZED']
			def env = nodevertical_properties['ENVIRONMENT']
			def token = nodevertical_properties['GITHUB_TOKEN']
	
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

			// Run nodevertical job
			try {
				nodevertical_build = build job: 'NODEVERTICAL-SCALE-TEST',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'USER', value: user ],
						[$class: 'StringParameterValue', name: 'TOOLING_INVENTORY', value: tooling_inventory_path ],
						[$class: 'BooleanParameterValue', name: 'CLEAR_RESULTS', value: Boolean.valueOf(clear_results) ],
						[$class: 'BooleanParameterValue', name: 'MOVE_RESULTS', value: Boolean.valueOf(move_results) ],	
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'StringParameterValue', name: 'ENVIRONMENT', value: env ],
						[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: token ],
						[$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ]]
			} catch ( Exception e) {
				echo "NODEVERTICAL-SCALE-TEST Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'Nodevertical-scale-test job failed',
					body: """\
						Encoutered an error while running the nodevertical-scale-test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
 				sh "exit 1"
			}
			println "NODE-VERTICAL-SCALE-TEST build ${nodevertical_build.getNumber()} completed successfully"
		}
	}
}

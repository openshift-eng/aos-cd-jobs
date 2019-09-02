#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def setup_tooling = SETUP_TOOLING.toString().toUpperCase()
def property_file_name = "set_pbench.properties"

println "Current pipeline job build id is '${pipeline_id}'"
// setup tooling
stage ('setup_pbench') {
	if (setup_tooling == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the property file already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${SETUP_PBENCH_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			def pbench_properties = readProperties file: property_file_name
			def jump_host = pbench_properties['JUMP_HOST']
			def user = pbench_properties['USER']
			def tooling_inventory_path = pbench_properties['TOOLING_INVENTORY']
			def openshift_inventory = pbench_properties['OPENSHIFT_INVENTORY']
			def use_proxy = pbench_properties['USE_PROXY']
			def proxy_user = pbench_properties['PROXY_USER']	
			def proxy_host = pbench_properties['PROXY_HOST']
			def containerized = pbench_properties['CONTAINERIZED']
			def all_nodes = pbench_properties['REGISTER_ALL_NODES']
			def token = pbench_properties['GITHUB_TOKEN']
			def repo = pbench_properties['PERF_REPO']
			def server = pbench_properties['PBENCH_SERVER']

			// copy the parameters file to jump host
			sh "git clone https://${token}@${repo} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
			sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${jump_host}:/root/properties"

			// debug info
			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "JUMP_HOST: '${jump_host}'"
			println "USER: '${user}'"
			println "TOOLING_INVENTORY_PATH: '${tooling_inventory_path}'"
			println "OPENSHIFT_INVENTORY_PATH: '${openshift_inventory}'"
			println "TOKEN: '${token}'"
			println "-------------------------------------------------"
			println "-------------------------------------------------"

			// Run setup-tooling job
			try {
				setup_pbench_build = build job: 'SETUP-TOOLING',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'USER', value: user ],
						[$class: 'StringParameterValue', name: 'TOOLING_INVENTORY', value: tooling_inventory_path ],															   [$class: 'StringParameterValue', name: 'OPENSHIFT_INVENTORY', value: openshift_inventory ],
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'BooleanParameterValue', name: 'REGISTER_ALL_NODES', value: Boolean.valueOf(all_nodes) ],
						[$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ],
						[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: token ]]
			} catch ( Exception e) {
				echo "SETUP_TOOLING Job failed with the following error: "
				echo "${e.getMessage()}"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'Setup-tooling job failed',
					body: """\
						Encoutered an error while running the setup-tooling job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
				sh "exit 1"
			}
			println "SETUP_TOOLING build ${setup_pbench_build.getNumber()} completed successfully"
		}
	}
}

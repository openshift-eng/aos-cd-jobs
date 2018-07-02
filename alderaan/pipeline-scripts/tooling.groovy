#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = 'CCI && ansible-2.4'
def setup_tooling = SETUP_TOOLING.toString().toUpperCase()

println "Current pipeline job build id is '${pipeline_id}'"
// setup tooling
stage ('setup_pbench') {
	if (setup_tooling == "TRUE") {
		currentBuild.result = "SUCCESS"
		node('CCI && US') {
			// get properties file
			if (fileExists("setup_pbench.properties")) {
				println "Looks like setup_pbench.properties file already exists, erasing it"
				sh "rm setup_pbench.properties"
			}
			// get properties file
			//sh "wget http://file.rdu.redhat.com/~nelluri/pipeline/setup_pbench.properties"
			sh "wget ${SETUP_PBENCH_PROPERTY_FILE} -O setup_pbench.properties"
			sh "cat setup_pbench.properties"
			def pbench_properties = readProperties file: "setup_pbench.properties"
			def jump_host = pbench_properties['JUMP_HOST']
			def user = pbench_properties['USER']
			def tooling_inventory_path = pbench_properties['TOOLING_INVENTORY']
			def openshift_inventory = pbench_properties['OPENSHIFT_INVENTORY']
			def use_proxy = pbench_properties['USE_PROXY']
			def proxy_user = pbench_properties['PROXY_USER']	
			def proxy_host = pbench_properties['PROXY_HOST']
			def containerized = pbench_properties['CONTAINERIZED']
			def all_nodes = pbench_properties['REGISTER_ALL_NODES']

			// debug info
			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "JUMP_HOST: '${jump_host}'"
			println "USER: '${user}'"
			println "TOOLING_INVENTORY_PATH: '${tooling_inventory_path}'"
			println "OPENSHIFT_INVENTORY_PATH: '${openshift_inventory}'"
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
						[$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ]]
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

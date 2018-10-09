#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def ns_per_cluster = NS_PER_CLUSTER.toString().toUpperCase()
def property_file_name = "ns_per_cluster.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run ns_per_cluster test
stage('ns_per_cluster_scale_test') {
	if (ns_per_cluster == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the property file already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${NS_PER_CLUSTER_PROPERTY_FILE} -O ${property_file_name}"
                        sh "cat ${property_file_name}"
			def ns_per_cluster_properties = readProperties file: property_file_name
			def jump_host = ns_per_cluster_properties['JUMP_HOST']
			def user = ns_per_cluster_properties['USER']
			def tooling_inventory_path = ns_per_cluster_properties['TOOLING_INVENTORY']
			def clear_results = ns_per_cluster_properties['CLEAR_RESULTS']
			def move_results = ns_per_cluster_properties['MOVE_RESULTS']
			def containerized = ns_per_cluster_properties['CONTAINERIZED']
			def use_proxy = ns_per_cluster_properties['USE_PROXY']
			def proxy_user = ns_per_cluster_properties['PROXY_USER']
			def proxy_host = ns_per_cluster_properties['PROXY_HOST']
			def projects = ns_per_cluster_properties['PROJECTS']
			def setup_pbench = ns_per_cluster_properties['SETUP_PBENCH']
			def first_run = ns_per_cluster_properties['FIRST_RUN_PROJECTS']
			def second_run = ns_per_cluster_properties['SECOND_RUN_PROJECTS']
			def third_run = ns_per_cluster_properties['THIRD_RUN_PROJECTS']

			// debug info
			println "JUMP_HOST: '${jump_host}'"
			println "USER: '${user}'"
			println "TOOLING_INVENTORY_PATH: '${tooling_inventory_path}'"
			println "CLEAR_RESULTS: '${clear_results}'"
			println "MOVE_RESULTS: '${move_results}'"
			println "CONTAINERIZED: '${containerized}'"
			println "PROXY_USER: '${proxy_user}'"
			println "PROXY_HOST: '${proxy_host}'"

			// Run ns_per_clusterical job
			try {
				ns_per_clusterical_build = build job: 'NS_PER_CLUSTER',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'USER', value: user ],
						[$class: 'StringParameterValue', name: 'TOOLING_INVENTORY', value: tooling_inventory_path ],
						[$class: 'BooleanParameterValue', name: 'CLEAR_RESULTS', value: Boolean.valueOf(clear_results) ],
						[$class: 'BooleanParameterValue', name: 'MOVE_RESULTS', value: Boolean.valueOf(move_results) ],
						[$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'BooleanParameterValue', name: 'SETUP_PBENCH', value: Boolean.valueOf(setup_pbench) ],
						[$class: 'StringParameterValue', name: 'FIRST_RUN_PROJECTS', value: first_run ],
						[$class: 'StringParameterValue', name: 'SECOND_RUN_PROJECTS', value: second_run ],
						[$class: 'StringParameterValue', name: 'THIRD_RUN_PROJECTS', value: third_run ]]
			} catch ( Exception e) {
				echo "NS_PER_CLUSTER Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
      					to: 'nelluri@redhat.com',
      					subject: 'NS_PER_CLUSTER job failed',
      					body: """\
						Encoutered an error while running the ns_per_clusterical-scale-test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
				sh "exit 1"
			}
			println "NS_PER_CLUSTER build ${ns_per_clusterical_build.getNumber()} completed successfully"
		}
	}
}

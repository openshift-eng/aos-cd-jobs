#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def byo = BYO_SCALE_TEST.toString().toUpperCase()
def property_file_name = "byo.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run nodevertical scale test
stage ('byo_scale_test') {
	if (byo == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the property file already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${BYO_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			def byo_properties = readProperties file: property_file_name
			def jump_host = byo_properties['JUMP_HOST']
			def user = byo_properties['USER']
			def use_proxy = byo_properties['USE_PROXY']
			def proxy_user = byo_properties['PROXY_USER']
			def proxy_host = byo_properties['PROXY_HOST']
			def containerized = byo_properties['CONTAINERIZED']
			def token = byo_properties['GITHUB_TOKEN']
			def repo = byo_properties['PERF_REPO']
			def server = byo_properties['PBENCH_SERVER']
			def byo_path = byo_properties['BYO_SCRIPT_PATH'] 
	
			// debug info
			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "JUMP_HOST: '${jump_host}'"
			println "BYO_SCRIPT_PATH: '${byo_path}'"
			println "USER: '${user}'"
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

			// Run nodevertical job
			try {
				byo_build = build job: 'BYO-SCALE-TEST',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'USER', value: user ],
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: token ],
						[$class: 'StringParameterValue', name: 'BYO_SCRIPT_PATH', value: byo_path ],
						[$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ]]
			} catch ( Exception e) {
				echo "BYO-SCALE-TEST Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'BYO-SCALE-TEST job failed',
					body: """\
						Encoutered an error while running the byo-scale-test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
 				sh "exit 1"
			}
			println "BYO-SCALE-TEST build ${byo_build.getNumber()} completed successfully"
		}
	}
}

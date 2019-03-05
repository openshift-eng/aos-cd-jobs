#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def prometheus_test = PROMETHEUS_TEST.toString().toUpperCase()
def property_file_name = "prometheus.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run prometheus scale test
stage ('prometheus_scale_test') {
	if ( prometheus_test == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			if (fileExists(property_file_name)) {
				println "prometheus.properties file exist... deleting it..."
				sh "rm ${property_file_name}"
			}
			sh "wget -O ${property_file_name} ${PROMETHEUS_PROPERTY_FILE}"
			sh "cat ${property_file_name}"
			def prometheus_properties = readProperties file: property_file_name
			def JUMP_HOST = prometheus_properties['JUMP_HOST']
			def USER = prometheus_properties['USER']
			def CLEAR_RESULTS = prometheus_properties['CLEAR_RESULTS']
			def MOVE_RESULTS = prometheus_properties['MOVE_RESULTS']
			def USE_PROXY = prometheus_properties['USE_PROXY']
			def CONTAINERIZED = prometheus_properties['CONTAINERIZED']
			def PROXY_USER = prometheus_properties['PROXY_USER']
			def PROXY_HOST = prometheus_properties['PROXY_HOST']
			def GITHUB_TOKEN = prometheus_properties['GITHUB_TOKEN']
			def PERF_REPO = prometheus_properties['PERF_REPO']
			def PBENCH_SERVER = prometheus_properties['PBENCH_SERVER']
			def SCALE_CI_RESULTS_TOKEN = prometheus_properties['SCALE_CI_RESULTS_TOKEN']
			def JOB = prometheus_properties['JOB']
			def REFRESH_INTERVAL = prometheus_properties['REFRESH_INTERVAL']
			def CONCURRENCY = prometheus_properties['CONCURRENCY']
			def GRAPH_PERIOD = prometheus_properties['GRAPH_PERIOD']
			def DURATION = prometheus_properties['DURATION']
			def TEST_NAME = prometheus_properties['TEST_NAME']

			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "JUMP_HOST: '${JUMP_HOST}'"
			println "USER: '${USER}'"
			println "CLEAR_RESULTS: '${CLEAR_RESULTS}'"
			println "MOVE_RESULTS: '${MOVE_RESULTS}'"
			println "USE_PROXY: '${USE_PROXY}'"
			println "CONTAINERIZED: '${CONTAINERIZED}'"
			println "PROXY_USER: '${PROXY_USER}'"
			println "PROXY_HOST: '${PROXY_HOST}'"
			println "GITHUB_TOKEN: '${GITHUB_TOKEN}'"
			println "PERF_REPO: '${PERF_REPO}'"
			println "PBENCH_SERVER: '${PBENCH_SERVER}'"
			println "SCALE_CI_RESULTS_TOKEN: '${SCALE_CI_RESULTS_TOKEN}'"
			println "JOB: '${JOB}'"
			println "REFRESH_INTERVAL: '${REFRESH_INTERVAL}'"
			println "CONCURRENCY: '${CONCURRENCY}'"
			println "GRAPH_PERIOD: '${GRAPH_PERIOD}'"
			println "TEST_NAME: '${TEST_NAME}'"
			println "DURATION: '${DURATION}'"
			println "-------------------------------------------------"
			println "-------------------------------------------------"

			// copy the parameters file to jump host
			sh "git clone https://${GITHUB_TOKEN}@${PERF_REPO} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
			sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${JUMP_HOST}:/root/properties"

			try {
				prometheus_build = build job: '${JOB}',
				parameters: [
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: JUMP_HOST ],
						[$class: 'StringParameterValue', name: 'USER', value: USER ],
						[$class: 'StringParameterValue', name: 'CLEAR_RESULTS', value: CLEAR_RESULTS ],
						[$class: 'StringParameterValue', name: 'MOVE_RESULTS', value: MOVE_RESULTS ],
						[$class: 'StringParameterValue', name: 'USE_PROXY', value: USE_PROXY ],
						[$class: 'StringParameterValue', name: 'CONTAINERIZED', value: CONTAINERIZED ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: PROXY_USER ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: PROXY_HOST ],
						[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: GITHUB_TOKEN ],
						[$class: 'StringParameterValue', name: 'PERF_REPO', value: PERF_REPO ],
						[$class: 'StringParameterValue', name: 'PBENCH_SERVER', value: PBENCH_SERVER ],
						[$class: 'StringParameterValue', name: 'SCALE_CI_RESULTS_TOKEN', value: SCALE_CI_RESULTS_TOKEN ],
						[$class: 'StringParameterValue', name: 'JOB', value: JOB ],
						[$class: 'StringParameterValue', name: 'REFRESH_INTERVAL', value: REFRESH_INTERVAL ],
						[$class: 'StringParameterValue', name: 'CONCURRENCY', value: CONCURRENCY ],
						[$class: 'StringParameterValue', name: 'GRAPH_PERIOD', value: GRAPH_PERIOD ],
						[$class: 'StringParameterValue', name: 'TEST_NAME', value: TEST_NAME ],
						[$class: 'StringParameterValue', name: 'DURATION', value: DURATION ]]
			} catch ( Exception e) {
				echo "${JOB} Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'sejug@redhat.com, nelluri@redhat.com',
					subject: '${JOB} job failed',
					body: """\
						Encoutered an error while running the ${JOB} job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
				sh "exit 1"
			}
			println "${JOB} build ${prometheus_build.getNumber()} completed successfully"
		}
	}
}

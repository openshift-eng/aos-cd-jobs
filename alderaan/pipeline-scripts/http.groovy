#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def http_test = HTTP_TEST.toString().toUpperCase()
def property_file_name = "http_test.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run HTTP test
stage('http_test_scale_test') {
	if (HTTP_TEST) {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the propertyfile already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${HTTP_TEST_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			def http_test_properties = readProperties file: property_file_name

			// test properties
			def containerized = http_test_properties['CONTAINERIZED']
			def jump_host = http_test_properties['JUMP_HOST']
			def jump_host_user = http_test_properties['JUMP_HOST_USER']
			def use_proxy = http_test_properties['USE_PROXY']
			def proxy_host = http_test_properties['PROXY_HOST']
			def proxy_user = http_test_properties['PROXY_USER']
			def test_cfg = http_test_properties['TEST_CFG']
			def kubeconfig = http_test_properties['KUBECONFIG']
			def pbench_use = http_test_properties['PBENCH_USE']
			def pbench_scraper_use = http_test_properties['PBENCH_SCRAPER_USE']
			def clear_results = http_test_properties['CLEAR_RESULTS']
			def move_results = http_test_properties['MOVE_RESULTS']
			def server_results = http_test_properties['SERVER_RESULTS']
			def server_results_ssh_key = http_test_properties['SERVER_RESULTS_SSH_KEY']
			def load_generators = http_test_properties['LOAD_GENERATORS']
			def load_generator_nodes = http_test_properties['LOAD_GENERATOR_NODES']
			def cl_projects = http_test_properties['CL_PROJECTS']
			def cl_templates = http_test_properties['CL_TEMPLATES']
			def run_time = http_test_properties['RUN_TIME']
			def mb_delay = http_test_properties['MB_DELAY']
			def mb_tls_session_reuse = http_test_properties['MB_TLS_SESSION_REUSE']
			def mb_method = http_test_properties['MB_METHOD']
			def mb_response_size = http_test_properties['MB_RESPONSE_SIZE']
			def mb_request_body_size = http_test_properties['MB_REQUEST_BODY_SIZE']
			def route_termination = http_test_properties['ROUTE_TERMINATION']
			def smoke_test = http_test_properties['SMOKE_TEST']
			def namespace_cleanup = http_test_properties['NAMESPACE_CLEANUP']
			def token = http_test_properties['GITHUB_TOKEN']
			def repo = http_test_properties['PERF_REPO']

			// debug info
			println "CONTAINERIZED: '${containerized}'"
			println "JUMP_HOST: '${jump_host}'"
			println "JUMP_HOST_USER: '${jump_host_user}'"
			println "USE_PROXY: '${use_proxy}'"
			println "PROXY_HOST: '${proxy_host}'"
			println "PROXY_USER: '${proxy_user}'"
			println "TEST_CFG: '${test_cfg}'"
			println "KUBECONFIG: '${kubeconfig}'"
			println "PBENCH_USE: '${pbench_use}'"
			println "PBENCH_SCRAPER_USE: '${pbench_scraper_use}'"
			println "CLEAR_RESULTS: '${clear_results}'"
			println "MOVE_RESULTS: '${move_results}'"
			println "SERVER_RESULTS: '${server_results}'"
			println "SERVER_RESULTS_SSH_KEY: '${server_results_ssh_key}'"
			println "LOAD_GENERATORS: '${load_generators}'"
			println "LOAD_GENERATOR_NODES: '${load_generator_nodes}'"
			println "CL_PROJECTS: '${cl_projects}'"
			println "CL_TEMPLATES: '${cl_templates}'"
			println "RUN_TIME: '${run_time}'"
			println "MB_DELAY: '${mb_delay}'"
			println "MB_TLS_SESSION_REUSE: '${mb_tls_session_reuse}'"
			println "MB_METHOD: '${mb_method}'"
			println "MB_RESPONSE_SIZE: '${mb_response_size}'"
			println "MB_REQUEST_BODY_SIZE: '${mb_request_body_size}'"
			println "ROUTE_TERMINATION: '${route_termination}'"
			println "SMOKE_TEST: '${smoke_test}'"
			println "NAMESPACE_CLEANUP: '${namespace_cleanup}'"

			// copy the parameters file to jump host
			sh "git clone https://${token}@${repo} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
			sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${jump_host}:/root/properties"

			// Run http_test job
			try {
				http_test_build = build job: 'http-scale-test',
				parameters: [	[$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST_USER', value: jump_host_user ],
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'TEST_CFG', value: test_cfg ],
						[$class: 'StringParameterValue', name: 'KUBECONFIG', value: kubeconfig ],
						[$class: 'BooleanParameterValue', name: 'PBENCH_USE', value: Boolean.valueOf(pbench_use) ],
						[$class: 'BooleanParameterValue', name: 'PBENCH_SCRAPER_USE', value: Boolean.valueOf(pbench_scraper_use) ],
						[$class: 'BooleanParameterValue', name: 'CLEAR_RESULTS', value: Boolean.valueOf(clear_results) ],
						[$class: 'BooleanParameterValue', name: 'MOVE_RESULTS', value: Boolean.valueOf(move_results) ],
						[$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ],
						[$class: 'StringParameterValue', name: 'SERVER_RESULTS', value: server_results ],
						[$class: 'StringParameterValue', name: 'SERVER_RESULTS_SSH_KEY', value: server_results_ssh_key ],
						[$class: 'StringParameterValue', name: 'LOAD_GENERATORS', value: load_generators ],
						[$class: 'StringParameterValue', name: 'LOAD_GENERATOR_NODES', value: load_generator_nodes ],
						[$class: 'StringParameterValue', name: 'CL_PROJECTS', value: cl_projects ],
						[$class: 'StringParameterValue', name: 'CL_TEMPLATES', value: cl_templates ],
						[$class: 'StringParameterValue', name: 'RUN_TIME', value: run_time ],
						[$class: 'StringParameterValue', name: 'MB_DELAY', value: mb_delay ],
						[$class: 'BooleanParameterValue', name: 'MB_TLS_SESSION_REUSE', value: Boolean.valueOf(mb_tls_session_reuse) ],
						[$class: 'StringParameterValue', name: 'MB_METHOD', value: mb_method ],
						[$class: 'StringParameterValue', name: 'MB_RESPONSE_SIZE', value: mb_response_size ],
						[$class: 'StringParameterValue', name: 'MB_REQUEST_BODY_SIZE', value: mb_request_body_size ],
						[$class: 'StringParameterValue', name: 'ROUTE_TERMINATION', value: route_termination ],
						[$class: 'BooleanParameterValue', name: 'SMOKE_TEST', value: Boolean.valueOf(smoke_test) ],
						[$class: 'BooleanParameterValue', name: 'NAMESPACE_CLEANUP', value: Boolean.valueOf(namespace_cleanup) ],
					    ]
			} catch (Exception e) {
				echo "HTTP scale-test Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'HTTP scale-test job failed',
					body: """\
					Encoutered an error while running the http_test-scale-test job: ${e.getMessage()}\n\n
					Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
				sh "exit 1"
			}
			println "HTTP_TEST-SCALE-TEST build ${http_test_build.getNumber()} completed successfully"
		}
	}
}

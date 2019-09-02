#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def pgbench_test = PGBENCH_TEST.toString().toUpperCase()
def property_file_name = "pgbench.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run pgbench scale test
stage ('pgbench_scale_test_glusterfs') {
	if ( pgbench_test == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			if (fileExists(property_file_name)) {
				println "pgbench_scale_test.properties file exist... deleting it..."
				sh "rm ${property_file_name}"
			}
			sh "wget -O ${property_file_name} ${PGBENCH_PROPERTY_FILE}"
			sh "cat ${property_file_name}"
			def pgbench_scale_test_properties = readProperties file: property_file_name
			def NAMESPACE = pgbench_scale_test_properties['NAMESPACE']
			def TRANSACTIONS = pgbench_scale_test_properties['TRANSACTIONS']
			def TEMPLATE = pgbench_scale_test_properties['TEMPLATE']
			def VOLUME_CAPACITY = pgbench_scale_test_properties['VOLUME_CAPACITY']
			def MEMORY_LIMIT = pgbench_scale_test_properties['MEMORY_LIMIT']
			def ITERATIONS = pgbench_scale_test_properties['ITERATIONS']
			def MODE = pgbench_scale_test_properties['MODE']
			def CLIENTS = pgbench_scale_test_properties['CLIENTS']
			def THREADS = pgbench_scale_test_properties['THREADS']
			def SCALING = pgbench_scale_test_properties['SCALING']
			def PBENCHCONFIG = pgbench_scale_test_properties['PBENCHCONFIG']
			def STORAGECLASS = pgbench_scale_test_properties['STORAGECLASS']
			def token = pgbench_scale_test_properties['GITHUB_TOKEN']
			def repo = pgbench_scale_test_properties['PERF_REPO']
			def server = pgbench_scale_test_properties['PBENCH_SERVER']

			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "NAMESPACE: '${NAMESPACE}'"
			println "TRANSACTIONS: '${TRANSACTIONS}'"
			println "TEMPLATE: '${TEMPLATE}'"
			println "VOLUME_CAPACITY: '${VOLUME_CAPACITY}'"
			println "MEMORY_LIMIT: '${MEMORY_LIMIT}'"
			println "ITERATIONS: '${ITERATIONS}'"
			println "MODE: '${MODE}'"
			println "CLIENTS: '${CLIENTS}'"
			println "THREADS: '${THREADS}'"
			println "SCALING: '${SCALING}'"
			println "PBENCHCONFIG: '${PBENCHCONFIG}'"
			println "STORAGECLASS: '${STORAGECLASS}'"
			println "-------------------------------------------------"
			println "-------------------------------------------------"

			// copy the parameters file to jump host
			sh "git clone https://${token}@${repo} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
			sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${jump_host}:/root/properties"

			try {
				pgbench_build = build job: 'PGBENCH_SCALE_TEST',
				parameters: [	[$class: 'StringParameterValue', name: 'NAMESPACE', value: NAMESPACE ],
						[$class: 'StringParameterValue', name: 'TRANSACTIONS', value: TRANSACTIONS ],
						[$class: 'StringParameterValue', name: 'TEMPLATE', value: TEMPLATE ],
						[$class: 'StringParameterValue', name: 'VOLUME_CAPACITY',value: VOLUME_CAPACITY ],
						[$class: 'StringParameterValue', name: 'MEMORY_LIMIT', value: MEMORY_LIMIT ],
						[$class: 'StringParameterValue', name: 'ITERATIONS', value: ITERATIONS ],
						[$class: 'StringParameterValue', name: 'MODE', value: MODE ],
						[$class: 'StringParameterValue', name: 'CLIENTS', value: CLIENTS ],
						[$class: 'StringParameterValue', name: 'THREADS', value: THREADS ],
						[$class: 'StringParameterValue', name: 'SCALING', value: SCALING ],
						[$class: 'StringParameterValue', name: 'PBENCHCONFIG', value: PBENCHCONFIG ],
						[$class: 'StringParameterValue', name: 'STORAGECLASS', value: STORAGECLASS ]]
						} catch ( Exception e) {
				echo "PGBENCH_SCALE_TEST Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'ekuric@redhat.com',
					subject: 'pgbench-scale-test job failed',
					body: """\
						Encoutered an error while running the pgbench-scale-test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
				sh "exit 1"
			}
			println "PGBENCH_SCALE_TEST build ${pgbench_build.getNumber()} completed successfully"
		}
	}
}

// run pgbench gluster-block scale test
stage ('pgbench_scale_test_gluster_block') {
		if ( pgbench_test == "TRUE") {
		currentBuild.result = "SUCCESS"
		node('CCI && US') {
			if (fileExists("pgbench_cns_block.properties")) {
				println "pgbench_cns_block.properties file exist... deleting it..."
				sh "rm pgbench_cns_block.properties"
			}
			sh "wget -O pgbench_cns_block.properties ${PGBENCH_PROPERTY_FILE_GLUSTER_BLOCK}"
			sh "cat pgbench_cns_block.properties"
			def pgbench_scale_test_properties = readProperties file: "pgbench_cns_block.properties"
			def NAMESPACE = pgbench_scale_test_properties['NAMESPACE']
			def TRANSACTIONS = pgbench_scale_test_properties['TRANSACTIONS']
			def TEMPLATE = pgbench_scale_test_properties['TEMPLATE']
			def VOLUME_CAPACITY = pgbench_scale_test_properties['VOLUME_CAPACITY']
			def MEMORY_LIMIT = pgbench_scale_test_properties['MEMORY_LIMIT']
			def ITERATIONS = pgbench_scale_test_properties['ITERATIONS']
			def MODE = pgbench_scale_test_properties['MODE']
			def CLIENTS = pgbench_scale_test_properties['CLIENTS']
			def THREADS = pgbench_scale_test_properties['THREADS']
			def SCALING = pgbench_scale_test_properties['SCALING']
			def PBENCHCONFIG = pgbench_scale_test_properties['PBENCHCONFIG']
			def STORAGECLASS = pgbench_scale_test_properties['STORAGECLASS']
			def token = pgbench_scale_test_properties['GITHUB_TOKEN']
			def repo = pgbench_scale_test_properties['PERF_REPO']
			def server = pgbench_scale_test_properties['PBENCH_SERVER']

			// debug info
			println "----------USER DEFINED OPTIONS-------------------"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			println "NAMESPACE: '${NAMESPACE}'"
			println "TRANSACTIONS: '${TRANSACTIONS}'"
			println "TEMPLATE: '${TEMPLATE}'"
			println "VOLUME_CAPACITY: '${VOLUME_CAPACITY}'"
			println "MEMORY_LIMIT: '${MEMORY_LIMIT}'"
			println "ITERATIONS: '${ITERATIONS}'"
			println "MODE: '${MODE}'"
			println "CLIENTS: '${CLIENTS}'"
			println "THREADS: '${THREADS}'"
			println "SCALING: '${SCALING}'"
			println "PBENCHCONFIG: '${PBENCHCONFIG}'"
			println "STORAGECLASS: '${STORAGECLASS}'"
			println "-------------------------------------------------"
			println "-------------------------------------------------"
			
			// copy the parameters file to jump host
			sh "git clone https://${token}@${repo} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
			sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${jump_host}:/root/properties"

			try {
				pgbench_build = build job: 'PGBENCH_SCALE_TEST',
				parameters: [	[$class: 'StringParameterValue', name: 'NAMESPACE', value: NAMESPACE ],
						[$class: 'StringParameterValue', name: 'TRANSACTIONS', value: TRANSACTIONS ],
						[$class: 'StringParameterValue', name: 'TEMPLATE', value: TEMPLATE ],
						[$class: 'StringParameterValue', name: 'VOLUME_CAPACITY',value: VOLUME_CAPACITY ],
						[$class: 'StringParameterValue', name: 'MEMORY_LIMIT', value: MEMORY_LIMIT ],
						[$class: 'StringParameterValue', name: 'ITERATIONS', value: ITERATIONS ],
						[$class: 'StringParameterValue', name: 'MODE', value: MODE ],
						[$class: 'StringParameterValue', name: 'CLIENTS', value: CLIENTS ],
						[$class: 'StringParameterValue', name: 'THREADS', value: THREADS ],
						[$class: 'StringParameterValue', name: 'SCALING', value: SCALING ],
						[$class: 'StringParameterValue', name: 'PBENCHCONFIG', value: PBENCHCONFIG ],
						[$class: 'StringParameterValue', name: 'STORAGECLASS', value: STORAGECLASS ]]
						} catch ( Exception e) {
							echo "PGBENCH_SCALE_TEST Job failed with the following error: "
							echo "${e.getMessage()}"
							echo "Sending an email"
							mail(
								to: 'ekuric@redhat.com',
								subject: 'pgbench-scale-test job failed',
								body: """\
										Encoutered an error while running the pgbench-scale-test job: ${e.getMessage()}\n\n
										Jenkins job: ${env.BUILD_URL}
						""")
						currentBuild.result = "FAILURE"
						sh "exit 1"
					}
					println "PGBENCH_SCALE_TEST build ${pgbench_build.getNumber()} completed successfully"
				}
		}
}

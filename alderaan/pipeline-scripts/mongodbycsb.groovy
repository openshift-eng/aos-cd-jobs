#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def mongodb_ycsb_test = MONGODB_YCSB_TEST.toString().toUpperCase()
def property_file_name = "mongodbycsb.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run mongoycsb scale test
stage ('mongoycsb_scale_test') {
		  if ( mongodb_ycsb_test == "TRUE") {
			currentBuild.result = "SUCCESS"
			node(node_label) {
				if (fileExists(property_file_name)) {
					println "Property file already exists... deleting it..."
					sh "rm ${property_file_name}"
				}
				sh "wget -O ${property_file_name} ${MONGOYCSB_PROPERTY_FILE}"
				sh "cat ${property_file_name}"
				
				def mongodbycsb_scale_test_properties = readProperties file: property_file_name
				def JUMP_HOST = mongodbycsb_scale_test_properties['JUMP_HOST']
				def USER = mongodbycsb_scale_test_properties['USER']
				def USE_PROXY = mongodbycsb_scale_test_properties['USE_PROXY']
				def PROXY_USER = mongodbycsb_scale_test_properties['PROXY_USER']
				def PROXY_HOST = mongodbycsb_scale_test_properties['PROXY_HOST']
				def SETUP_PBENCH = mongodbycsb_scale_test_properties['SETUP_PBENCH']
				def GITHUB_TOKEN = mongodbycsb_scale_test_properties['GITHUB_TOKEN']
				def PERF_REPO = mongodbycsb_scale_test_properties['PERF_REPO']
				def PBENCH_SERVER = mongodbycsb_scale_test_properties['PBENCH_SERVER']
				def CONTAINERIZED = mongodbycsb_scale_test_properties['CONTAINERIZED']
				def MEMORY_LIMIT = mongodbycsb_scale_test_properties['MEMORY_LIMIT']
				def YCSB_THREADS = mongodbycsb_scale_test_properties['YCSB_THREADS']
				def WORKLOAD = mongodbycsb_scale_test_properties['WORKLOAD']
				def ITERATION = mongodbycsb_scale_test_properties['ITERATION']
				def RECORDCOUNT = mongodbycsb_scale_test_properties['RECORDCOUNT']
				def OPERATIONCOUNT = mongodbycsb_scale_test_properties['OPERATIONCOUNT']
				def STORAGECLASS = mongodbycsb_scale_test_properties['STORAGECLASS']
				def VOLUMESIZE = mongodbycsb_scale_test_properties['VOLUMESIZE']
				def DISTRIBUTION = mongodbycsb_scale_test_properties['DISTRIBUTION']
				def PROJECTS = mongodbycsb_scale_test_properties['PROJECTS']

				// debug info
				println "----------USER DEFINED OPTIONS-------------------"
				println "-------------------------------------------------"
				println "-------------------------------------------------"
				println "JUMP_HOST: '${JUMP_HOST}'"
				println "USER: '${USER}"
				println "USE_PROXY: '${USE_PROXY}'"
				println "PROXY_USER: '${PROXY_USER}'"
				println "PROXY_HOST": '${PROXY_HOST}'
				println "SETUP_PBENCH: '${SETUP_PBENCH}'"
				println "CONTAINERIZED:'${CONTAINERIZED}'"
				println "MEMORY_LIMIT: '${MEMORY_LIMIT}'"
				println "YCSB_THREADS: '${YCSB_THREADS}'"
				println "WORKLOAD: '${WORKLOAD}'"
				println "ITERATION: '${ITERATION}'"
				println "RECORDCOUNT: '${RECORDCOUNT}'"
				println "OPERATIONCOUNT: '${OPERATIONCOUNT}'"
				println "STORAGECLASS: '${STORAGECLASS}'"
				println "VOLUMESIZE:'${VOLUMESIZE}'"
				println "DISTRIBUTION: '${DISTRIBUTION}'"
				println "PROJECTS: '${PROJECTS}'"
				println "-------------------------------------------------"
				println "-------------------------------------------------"

				sh "git clone https://${token}@${repo} ${WORKSPACE}/perf-dept && chmod 600 ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf"
				sh "scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${WORKSPACE}/perf-dept/ssh_keys/id_rsa_perf ${property_file_name} root@${jump_host}:/root/properties"

				try {
					mongodbycsb_build = build job: 'MONGODB_YCSB_TEST',
					parameters: [	
							[$class: 'StringParameterValue', name: 'JUMP_HOST', value: JUMP_HOST ],
							[$class: 'StringParameterValue', name: 'USER', value: USER ],
							[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(USE_PROXY) ],
							[$class: 'StringParameterValue', name: 'PROXY_USER', value: PROXY_USER ],
							[$class: 'StringParameterValue', name: 'PROXY_HOST', value: PROXY_HOST ],
							[$class: 'BooleanParameterValue', name: 'SETUP_PBENCH', value: Boolean.valueOf(SETUP_PBENCH) ],
							[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: GITHUB_TOKEN ],
							[$class: 'StringParameterValue', name: 'PERF_REPO', value: PERF_REPO ],
							[$class: 'StringParameterValue', name: 'PBENCH_SERVER', value: PBENCH_SERVER ],
							[$class: 'StringParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(CONTAINERIZED) ],
							[$class: 'StringParameterValue', name: 'MEMORY_LIMIT', value: MEMORY_LIMIT ],
							[$class: 'StringParameterValue', name: 'YCSB_THREADS', value: YCSB_THREADS ],
							[$class: 'StringParameterValue', name: 'WORKLOAD',value: WORKLOAD ],
							[$class: 'StringParameterValue', name: 'ITERATION', value: ITERATION ],
							[$class: 'StringParameterValue', name: 'RECORDCOUNT', value: RECORDCOUNT ],
							[$class: 'StringParameterValue', name: 'OPERATIONCOUNT', value: OPERATIONCOUNT ],
							[$class: 'StringParameterValue', name: 'STORAGECLASS', value: STORAGECLASS ],
							[$class: 'StringParameterValue', name: 'VOLUMESIZE', value: VOLUMESIZE ],
							[$class: 'StringParameterValue', name: 'DISTRIBUTION', value: DISTRIBUTION ],
							[$class: 'StringParameterValue', name: 'PROJECTS', value: PROJECTS ]]
						} catch ( Exception e) {
							echo "MONGODB_YCSB_TEST Job failed with the following error: "
							echo "${e.getMessage()}"
							echo "Sending an email"
							mail(
								to: 'ekuric@redhat.com',
								subject: 'mongodb-ycsb-test job failed',
								body: """\
									Encoutered an error while running the mongodb-ycsb-test job: ${e.getMessage()}\n\n
										Jenkins job: ${env.BUILD_URL}
						""")
						currentBuild.result = "FAILURE"
						sh "exit 1"
					}
					println "MONGODB_YCSB_TEST build ${mongodbycsb_build.getNumber()} completed successfully"
				}
		}
}

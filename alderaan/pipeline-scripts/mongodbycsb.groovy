#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
println "Current pipeline job build id is '${pipeline_id}'"
def node_label = 'CCI && ansible-2.3'
def mongodb_ycsb_test = MONGODB_YCSB_TEST.toString().toUpperCase()

// run mongoycsb scale test
stage ('mongoycsb_scale_test_glusterfs') {
		  if ( mongodb_ycsb_test == "TRUE") {
			currentBuild.result = "SUCCESS"
			node('CCI && US') {
				if (fileExists("mongodbycsb.properties")) {
					println "mongodbycsb.properties... deleting it..."
					sh "rm mongodbycsb.properties"
				}
				sh "wget -O mongodbycsb.properties ${MONGOYCSB_PROPERTY_FILE}"
				sh "cat mongodbycsb.properties"
				def mongodbycsb_scale_test_properties = readProperties file: "mongodbycsb.properties"
				def MEMORY_LIMIT = mongodbycsb_scale_test_properties['MEMORY_LIMIT']
				def YCSB_THREADS = mongodbycsb_scale_test_properties['YCSB_THREADS']
				def WORKLOAD = mongodbycsb_scale_test_properties['WORKLOAD']
				def ITERATION = mongodbycsb_scale_test_properties['ITERATION']
				def RECORDCOUNT = mongodbycsb_scale_test_properties['RECORDCOUNT']
				def OPERATIONCOUNT = mongodbycsb_scale_test_properties['OPERATIONCOUNT']
				def STORAGECLASS = mongodbycsb_scale_test_properties['STORAGECLASS']
				def VOLUMESIZE = mongodbycsb_scale_test_properties['VOLUMESIZE']
				// debug info
				println "----------USER DEFINED OPTIONS-------------------"
				println "-------------------------------------------------"
				println "-------------------------------------------------"
				println "MEMORY_LIMIT: '${MEMORY_LIMIT}'"
				println "YCSB_THREADS: '${YCSB_THREADS}'"
				println "WORKLOAD: '${WORKLOAD}'"
				println "ITERATION: '${ITERATION}'"
				println "RECORDCOUNT: '${RECORDCOUNT}'"
				println "OPERATIONCOUNT: '${OPERATIONCOUNT}'"
				println "STORAGECLASS: '${STORAGECLASS}'"
				println "VOLUMESIZE:'${VOLUMESIZE}'"
				println "-------------------------------------------------"
				println "-------------------------------------------------"
				try {
					mongodbycsb_build = build job: 'MONGODB_YCSB_TEST',
					parameters: [	[$class: 'StringParameterValue', name: 'MEMORY_LIMIT', value: MEMORY_LIMIT ],
							[$class: 'StringParameterValue', name: 'YCSB_THREADS', value: YCSB_THREADS ],
							[$class: 'StringParameterValue', name: 'WORKLOAD',value: WORKLOAD ],
							[$class: 'StringParameterValue', name: 'ITERATION', value: ITERATION ],
							[$class: 'StringParameterValue', name: 'RECORDCOUNT', value: RECORDCOUNT ],
							[$class: 'StringParameterValue', name: 'OPERATIONCOUNT', value: OPERATIONCOUNT ],
							[$class: 'StringParameterValue', name: 'STORAGECLASS', value: STORAGECLASS ],
							[$class: 'StringParameterValue', name: 'VOLUMESIZE', value: VOLUMESIZE ]]
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

stage ('mongoycsb_scale_test_gluster_block') {
		  if ( mongodb_ycsb_test == "TRUE") {
			currentBuild.result = "SUCCESS"
			node('CCI && US') {
				// get properties file
				if (fileExists("mongodbycsbblock.properties")) {
					println "mongodbycsbblock.properties... deleting it..."
					sh "rm mongodbycsbblock.properties"
				}
				sh "wget -O mongodbycsbblock.properties ${MONGOYCSB_PROPERTY_FILE_GLUSTER_BLOCK}"
				sh "cat mongodbycsbblock.properties"
				def mongodbycsb_scale_test_properties = readProperties file: "mongodbycsbblock.properties"
				def MEMORY_LIMIT = mongodbycsb_scale_test_properties['MEMORY_LIMIT']
				def YCSB_THREADS = mongodbycsb_scale_test_properties['YCSB_THREADS']
				def WORKLOAD = mongodbycsb_scale_test_properties['WORKLOAD']
				def ITERATION = mongodbycsb_scale_test_properties['ITERATION']
				def RECORDCOUNT = mongodbycsb_scale_test_properties['RECORDCOUNT']
				def OPERATIONCOUNT = mongodbycsb_scale_test_properties['OPERATIONCOUNT']
				def STORAGECLASS = mongodbycsb_scale_test_properties['STORAGECLASS']
				def VOLUMESIZE = mongodbycsb_scale_test_properties['VOLUMESIZE']
				// debug info
				println "----------USER DEFINED OPTIONS-------------------"
				println "-------------------------------------------------"
				println "-------------------------------------------------"
				println "MEMORY_LIMIT: '${MEMORY_LIMIT}'"
				println "YCSB_THREADS: '${YCSB_THREADS}'"
				println "WORKLOAD: '${WORKLOAD}'"
				println "ITERATION: '${ITERATION}'"
				println "RECORDCOUNT: '${RECORDCOUNT}'"
				println "OPERATIONCOUNT: '${OPERATIONCOUNT}'"
				println "STORAGECLASS: '${STORAGECLASS}'"
				println "VOLUMESIZE:'${VOLUMESIZE}'"
				println "-------------------------------------------------"
				println "-------------------------------------------------"
				try {
					mongodbycsb_build = build job: 'MONGODB_YCSB_TEST',
					parameters: [	[$class: 'StringParameterValue', name: 'MEMORY_LIMIT', value: MEMORY_LIMIT ],
							[$class: 'StringParameterValue', name: 'YCSB_THREADS', value: YCSB_THREADS ],
							[$class: 'StringParameterValue', name: 'WORKLOAD',value: WORKLOAD ],
							[$class: 'StringParameterValue', name: 'ITERATION', value: ITERATION ],
							[$class: 'StringParameterValue', name: 'RECORDCOUNT', value: RECORDCOUNT ],
							[$class: 'StringParameterValue', name: 'OPERATIONCOUNT', value: OPERATIONCOUNT ],
							[$class: 'StringParameterValue', name: 'STORAGECLASS', value: STORAGECLASS ],
							[$class: 'StringParameterValue', name: 'VOLUMESIZE', value: VOLUMESIZE ]]
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


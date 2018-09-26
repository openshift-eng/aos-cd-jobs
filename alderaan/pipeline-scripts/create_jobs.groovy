#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def create_jobs = CREATE_JOBS_FROM_JJB.toString().toUpperCase()
def property_file_name = "jobs.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run jobs scale test
stage ('Create jobs in OpenShift QE jenkins') {
	if (create_jobs == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Looks like the file already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${JOBS_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			def jobs_properties = readProperties file: property_file_name
			def jump_host = jobs_properties['JUMP_HOST']
			def user = jobs_properties['USER']
			def use_proxy = jobs_properties['USE_PROXY']
			def proxy_user = jobs_properties['PROXY_USER']
			def proxy_host = jobs_properties['PROXY_HOST']
			def token = jobs_properties['GITHUB_TOKEN']
			def config = jobs_properties['CONFIG_PATH']
			def repo = jobs_properties['REPO']
	
			// Run the alderaan-create-jobs job
			try {
				jobs_build = build job: 'ALDERAAN-CREATE-JOBS',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
						[$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
						[$class: 'StringParameterValue', name: 'USER', value: user ],
						[$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
						[$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
						[$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
						[$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: token ],
						[$class: 'StringParameterValue', name: 'CONFIG_PATH', value: config ],
						[$class: 'StringParameterValue', name: 'REPO', value: repo ]]
			} catch ( Exception e) {
				echo "ALDERAAN-CREATE-JOBS Job failed with the following error: "
				echo "${e.getMessage()}"
				echo "Sending an email"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'ALDERAAN-CREATE-JOBS job failed',
					body: """\
						Encoutered an error while running the jobs-scale-test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
 				sh "exit 1"
			}
			println "ALDERAAN-CREATE-JOBS build ${jobs_build.getNumber()} completed successfully"
		}
	}

#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def node_label = NODE_LABEL.toString()
def browbeat = BROWBEAT_INSTALL.toString().toUpperCase()
def property_file_name = "browbeat.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run browbeat install
stage ('BROWBEAT') {
	if (browbeat == "TRUE") {
		currentBuild.result = "SUCCESS"
		node(node_label) {
			// get properties file
			if (fileExists(property_file_name)) {
				println "Properties file already exists, erasing it"
				sh "rm ${property_file_name}"
			}
			// get properties file
			sh "wget ${BROWBEAT_PROPERTY_FILE} -O ${property_file_name}"
			sh "cat ${property_file_name}"
			//Load the properties file
			def properties = readProperties file: property_file_name
			println(properties)
			def job_parameters = []
			job_parameters.add([$class: 'LabelParameterValue', name: 'node', label: node_label ])
			// Convert properties to parameters
			for (property in properties) {
				job_parameters.add([$class: 'StringParameterValue', name: property.key, value: property.value ])
			}
			println(job_parameters)
			// Run browbeat job
			try {
				browbeat_build = build job: 'scale-ci_install_Browbeat', parameters: job_parameters
				println "Browbeat build ${browbeat_build.getNumber()} completed successfully"
			} catch ( Exception e) {
				echo " Browbeat failed with the following error: "
				echo "${e.getMessage()}"
				mail(
					to: 'nelluri@redhat.com',
					subject: 'Browbeat job failed',
					body: """\
						Encoutered an error while running the browbeat job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
				currentBuild.result = "FAILURE"
				sh "exit 1"
			}
		}
	}
}

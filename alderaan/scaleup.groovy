#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
println "Current pipeline job build id is '${pipeline_id}'"
def node_label = 'CCI && ansible-2.4'
def scaleup = OPENSHIFT_SCALEUP.toString().toUpperCase()

// scaleup
stage ('openshift_scaleup') {
		currentBuild.result = "SUCCESS"
		node('CCI && US') {
			// get properties file
			if (fileExists("openshift_scaleup.properties")) {
				println "Looks like openshift_scaleup.properties file already exists, erasing it"
				sh "rm openshift_scaleup.properties"
			}
			// get properties file
			//sh  "wget http://file.rdu.redhat.com/~nelluri/pipeline/openshift_scaleup.properties"
			sh "wget ${OPENSHIFT_SCALEUP_PROPERTY_FILE} -O openshift_scaleup.properties"
			sh "cat openshift_scaleup.properties"
			def scaleup_properties = readProperties file: "openshift_scaleup.properties"
			def openstack_server = scaleup_properties['OPENSTACK_SERVER']
			def openstack_user = scaleup_properties['OPENSTACK_USER']
			def image_server = scaleup_properties['IMAGE_SERVER']
			def image_user = scaleup_properties['IMAGE_USER']
			def branch = scaleup_properties['BRANCH']
			def openshift_node_target = scaleup_properties['OPENSHIFT_NODE_TARGET']
			def block_size = scaleup_properties['SCALE_BLOCK_SIZE']
			def time_servers = scaleup_properties['TIME_SERVERS']
			def jenkins_slave_label = scaleup_properties['JENKINS_SLAVE_LABEL']

                        // debug info
                        println "----------USER DEFINED OPTIONS-------------------"
                        println "-------------------------------------------------"
                        println "-------------------------------------------------"
                        println "OPENSTACK_SERVER: '${openstack_server}'"
                        println "OPENSTACK_USER: '${openstack_user}'"
                        println "IMAGE_SERVER: '${image_server}'"
                        println "IMAGE_USER: '${image_user}'"
                        println "BRANCH: '${branch}'"
                        println "OPENSHIFT_NODE_TARGET: '${openshift_node_target}'"
                        println "TIME_SERVERS: '${time_servers}'"
                        println "JENKINS_SLAVE_LABEL: '${jenkins_slave_label}'"
                        println "-------------------------------------------------"
                        println "-------------------------------------------------"	
		
			// Run scaleup
			try {
			    scaleup_build = build job: 'scale-ci_ScaleUp_OpenShift',
				parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
                                                [$class: 'StringParameterValue', name: 'OPENSTACK_SERVER', value: openstack_server ],
                                                [$class: 'StringParameterValue', name: 'OPENSTACK_USER', value: openstack_user ],
                                                [$class: 'StringParameterValue', name: 'IMAGE_SERVER', value: image_server ],
                                                [$class: 'StringParameterValue', name: 'IMAGE_USER', value: image_user ],
                                                [$class: 'StringParameterValue', name: 'branch', value: branch ],
                                                [$class: 'StringParameterValue', name: 'OPENSHIFT_NODE_TARGET', value: openshift_node_target ],
                                                [$class: 'StringParameterValue', name: 'scale_block_size', value: block_size ],
                                                [$class: 'StringParameterValue', name: 'time_servers', value: time_servers ],
                                                [$class: 'StringParameterValue', name: 'JENKINS_SLAVE_LABEL', value: jenkins_slave_label ]]
			} catch ( Exception e) {
                	echo "SCALE_CI_OPENSHIFT_SCALEUP Job failed with the following error: "
                	echo "${e.getMessage()}"
			mail(
                                to: 'nelluri@redhat.com',
                                subject: 'Scaleup job failed',
                                body: """\
                                        Encoutered an error while running the scalup job: ${e.getMessage()}\n\n
                                        Jenkins job: ${env.BUILD_URL}
                        """)
                	currentBuild.result = "FAILURE"
			sh "exit 1"
            		}
                	println "SCALE-CI-OPENSHIFT-SCALEUP build ${openshift_build.getNumber()} completed successfully"
		}
}

#!/usr/bin/env groovy

def pipeline_id = env.BUILD_ID
def cnv_scale_test = CNV_SCALE_TEST.toString().toUpperCase()
def property_file_name = "cvn_scale_test.properties"

println "Current pipeline job build id is '${pipeline_id}'"

// run cvn scale test
stage ('cnv_scale_test') {
    if (cnv_scale_test == "TRUE") {
        currentBuild.result = "SUCCESS"
        node(node_label) {
            // get properties file
            if (fileExists(property_file_name)) {
                println "Looks like the property file already exists, erasing it"
                sh "rm ${property_file_name}"
            }
            // get properties file
            sh "wget ${CNV_SCALE_TEST} -O ${property_file_name}"
            sh "cat ${property_file_name}"
            def cvn_scale_test_properties = readProperties file: property_file_name
            def jump_host = cvn_scale_test_properties['JUMP_HOST']
            def user = cvn_scale_test_properties['USER']
            def tooling_inventory_path = cvn_scale_test_properties['TOOLING_INVENTORY']
            def clear_results = cvn_scale_test_properties['CLEAR_RESULTS']
            def move_results = cvn_scale_test_properties['MOVE_RESULTS']
            def use_proxy = cvn_scale_test_properties['USE_PROXY']
            def proxy_user = cvn_scale_test_properties['PROXY_USER']
            def proxy_host = cvn_scale_test_properties['PROXY_HOST']
            def containerized = cvn_scale_test_properties['CONTAINERIZED']
            def env = cvn_scale_test_properties['ENVIRONMENT']
            def token = cvn_scale_test_properties['GITHUB_TOKEN']

            // debug info
            println "----------USER DEFINED OPTIONS-------------------"
            println "-------------------------------------------------"
            println "-------------------------------------------------"
            println "JUMP_HOST: '${jump_host}'"
            println "USER: '${user}'"
            println "TOOLING_INVENTORY_PATH: '${tooling_inventory_path}'"
            println "CLEAR_RESULTS: '${clear_results}'"
            println "MOVE_RESULTS: '${move_results}'"
            println "USE_PROXY: '${use_proxy}'"
            println "PROXY_USER: '${proxy_user}'"
            println "PROXY_HOST: '${proxy_host}'"
            println "CONTAINERIZED: '${containerized}'"
            println "TOKEN: '${token}'"
            println "-------------------------------------------------"
            println "-------------------------------------------------"

            // Run cnv_scale_test job
            try {
                cnv_scale_test_build = build job: 'CNV-SCALE-TEST',
                        parameters: [   [$class: 'LabelParameterValue', name: 'node', label: node_label ],
                                        [$class: 'StringParameterValue', name: 'JUMP_HOST', value: jump_host ],
                                        [$class: 'StringParameterValue', name: 'USER', value: user ],
                                        [$class: 'StringParameterValue', name: 'TOOLING_INVENTORY', value: tooling_inventory_path ],
                                        [$class: 'BooleanParameterValue', name: 'CLEAR_RESULTS', value: Boolean.valueOf(clear_results) ],
                                        [$class: 'BooleanParameterValue', name: 'MOVE_RESULTS', value: Boolean.valueOf(move_results) ],
                                        [$class: 'BooleanParameterValue', name: 'USE_PROXY', value: Boolean.valueOf(use_proxy) ],
                                        [$class: 'StringParameterValue', name: 'PROXY_USER', value: proxy_user ],
                                        [$class: 'StringParameterValue', name: 'PROXY_HOST', value: proxy_host ],
                                        [$class: 'StringParameterValue', name: 'ENVIRONMENT', value: env ],
                                        [$class: 'StringParameterValue', name: 'GITHUB_TOKEN', value: token ],
                                        [$class: 'BooleanParameterValue', name: 'CONTAINERIZED', value: Boolean.valueOf(containerized) ]]
            } catch ( Exception e) {
                echo "CNV-SCALE-TEST Job failed with the following error: "
                echo "${e.getMessage()}"
                echo "Sending an email"
                mail(
                        to: 'nelluri@redhat.com', 'ipinto@redhat.com', 'msivak@redhat.com', 'xlisovsk@redhat.com', 'guchen@redhat.com',
                        subject: 'CVN-scale-test job failed',
                        body: """\
						Encoutered an error while running the cnv scale test job: ${e.getMessage()}\n\n
						Jenkins job: ${env.BUILD_URL}
				""")
                currentBuild.result = "FAILURE"
                sh "exit 1"
            }
            println "CNV-SCALE-TEST build ${cnv_scale_test_build.getNumber()} completed successfully"
        }
    }
}

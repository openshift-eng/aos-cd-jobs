

node('covscan') {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib

    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '365',
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION'),
                    /*string(
                        name: 'NVRA',
                        description: 'The brew nvr for the srpm. e.g. openshift-clients-4.3.3-202002192116.git.1.18d8f2b.el7',
                        trim: false
                    ),*/
                    string(
                        name: 'BREW_TASK_ID',
                        description: 'Brew build task for the RPM',
                        trime: true,
                    ),
                    booleanParam(   defaultValue: false,
                                    description: 'Force a rescan of the codebase even if it was already performed',
                                    name: 'RE_SCAN'),
                    booleanParam(   defaultValue: false,
                                    description: 'Force re-prompting for waiver information',
                                    name: 'RE_WAIVE'),
                    booleanParam(   defaultValue: false,
                                    description: 'If true, waivers from previous scans will not be used to determine issues (i.e. all issues will be reported).',
                                    name: 'IGNORE_PREVIOUS'),
                    commonlib.mockParam(),
                ],
            ],
        ]
    )

    commonlib.checkMock()

    timestamps {

        def (major, minor) = commonlib.extractMajorMinorVersionNumbers(BUILD_VERSION)
        def imageName = "golang-scanner-${BUILD_VERSION}"

        slackChannel = slacklib.to(BUILD_VERSION)

        sshagent(['openshift-bot']) {

            RUN_DATE = sh(returnStdout: true, script:'date "+%s"')
            WORK_COV = "${env.WORKSPACE}/cov"
            WORK_RPM = "${env.WORKSPACE}/rpm"

            NVRA = null
            BUILD_TAG = null
            BREW_TASK_INFO = sh(returnStdout: true, script:"brew taskinfo ${BREW_TASK_ID} -rv")
            for ( String taskLine: BREW_TASK_INFO.split('\n') ) {
                taskLine = taskLine.trim()

                // Look for a line like: SRPM: /mnt/redhat/brewroot/work/tasks/4600/27044600/openshift-clients-4.5.0-202003050701.git.0.06478dc.el7.src.rpm
                if ( taskLine.startsWith('SRPM: ') ) {
                    echo "Extracting NVRA from ${taskLine}"
                    NVRA = taskLine.split('/')[-1].split('.src')[0]
                    continue
                }

                // Look for a line like: Build Tag: rhaos-4.5-rhel-7-build
                if ( taskLine.startsWith('Build Tag: ') ) {
                    echo "Extracting BUILD_TAG from: ${taskLine}"
                    BUILD_TAG = taskLine.split(':')[1].trim()
                }
            }

            if ( NVRA == null || BUILD_TAG == null ) {
                error("I could not find NVRA or BUILD_TAG in taskinfo for ${BREW_TASK_ID}:\n${BREW_TASK_INFO}")
            }

            if (BUILD_TAG.contains('-rhel-7-')) {
                MOCK_PROFILE = readFile(file: 'jobs/scanning/scan-srpm/base-rhel-7-mock-profile.cfg')
            } else {
                // More profiles can be found here: https://gitlab.cee.redhat.com/covscan/mock-profiles/tree/master/src
                error("I don't have a profile yet for for ${BUILD_TAG}")
            }

            // Update the mock profile to contain the buildroot repo used by the task
            // If this hardcoded pattern doesn't work, maybe using something like "brew mock-config --task 27044635 --latest" would be better in the long run.
            MOCK_PROFILE = MOCK_PROFILE.replace('#PIPELINE_INJECT_REPOS#', """
[${BUILD_TAG}]
name=${BUILD_TAG}
gpgcheck=0
baseurl=http://download.eng.bos.redhat.com/brewroot/repos/${BUILD_TAG}/latest/x86_64/
priority=255
""")

            // Example output: /mnt/redhat/brewroot/vol/rhel-7/packages/openshift-clients/4.3.3/202002192116.git.1.18d8f2b.el7/src/openshift-clients-4.3.3-202002192116.git.1.18d8f2b.el7.src.rpm
            NFS_SRPM_PATH = sh(returnStdout: true, script:"brew buildinfo ${NVRA} | grep src.rpm").trim()
            SRPM_FILENAME = sh(returnStdout: true, script:"basename ${NFS_SRPM_PATH}").trim()
            (SRPM_N, SRPM_V, SRPM_R, SRPM_A) = sh(returnStdout: true, script:"rpm -qp --queryformat '%{NAME} %{VERSION} %{RELEASE} %{ARCH}' ${NFS_SRPM_PATH}").split()

            sh """
            set -euxo pipefail
            sudo rm -rf ${WORK_COV} ${WORK_RPM}
            mkdir -p ${WORK_COV} ${WORK_RPM}
            cp ${NFS_SRPM_PATH} ${WORK_RPM}
            """

            dir('rpm') {
                writeFile(file: "${BUILD_TAG}.cfg", text: MOCK_PROFILE)
            }

            currentBuild.displayName = "${currentBuild.displayName} - ${BREW_TASK_ID}: ${SRPM_FILENAME}"

            SCANS_BASE_DIR = '/mnt/nfs/coverity/scans'
            NVR="${SRPM_N}-${SRPM_V}-{SRPM_R}"

            NVR_SCAN_DIR = "${SCANS_BASE_DIR}/${NVR}"  // presence indicates a scan has been performed
            WAIVED_BASE_DIR = '/mnt/nfs/coverity/waived'
            NVR_WAIVED_DIR = "${WAIVED_BASE_DIR}/${NVR}"  // presence indicates issues have been waived

            stage('scan') {
                sh "mkdir -p ${SCANS_BASE_DIR}"
                sh "mkdir -p ${WAIVED_BASE_DIR}"

                if ( fileExists("${NVR_SCAN_DIR}")) {
                    if ( params.RE_SCAN ) {
                        sh "rm -rf ${NVR_SCAN_DIR} ${NVR_WAIVED_DIR}"
                    } else {
                        echo "Detected ${NVR_SCAN_DIR} . Scan has already been performed. Skipping ."
                        return // jump to the end of the stage
                    }
                }

                imageName = "golang-scanner-${BUILD_VERSION}"

                sh """
                set -euxo pipefail
                # mock doesn't run well without a privileged container. -r argument must be the base filename of a file in /etc/mock. It is copied into place as we launch the container.
                sudo podman run --privileged -t --rm -v ${WORK_RPM}:/rpm -v ${WORK_COV}:/cov ${imageName} /bin/sh -c 'export PATH=\$PATH:/opt/coverity/bin; cp rpm/${BUILD_TAG}.cfg /etc/mock; csmock -o /cov/output -r ${BUILD_TAG} --force --cov-analyze-java --cov-analyze-opts="--security --concurrency" --use-host-cppcheck /rpm/${SRPM_FILENAME}'

                export PATH=\$PATH:/opt/coverity/bin
                
                # These steps let us re-use code from the git scanning pipeline. 
                mv ./cov/output/* ./cov
                mv ./cov/scan_results.js ./cov/raw_results.js       
                
                cshtml ./cov/raw_results.js > ./cov/raw_results.html
                """

                archiveArtifacts(artifacts: "cov/*_results.*")

                // Copy the scan results to the NFS. This only indicates the code has been scanned. No waiver is implied.
                sh """
                mkdir -p ${NVR_SCAN_DIR}
                cp cov/*_results.* ${NVR_SCAN_DIR}   # A full covscan emit can be gigs, so only copy results.
                """
            }


            stage('waive') {

                if ( fileExists( NVR_WAIVED_DIR ) && params.RE_WAIVE == false ) {
                    echo "Detected ${NVR_WAIVED_DIR}. Issues have already been waived. Skipping waiver input."
                    return // end the stage
                }

                sh """
                # If case we don't find anything, diff results are the same as raw results
                cp ${NVR_SCAN_DIR}/raw_results.js ${NVR_SCAN_DIR}/diff_results.js

                if [[ "${params.IGNORE_PREVIOUS}" == "false" ]]; then
                    cd ${WAIVED_BASE_DIR}
                    
                    # Here's the theory -- if we sort by NVR by version & release, the version directly BEFORE
                    # the one is one that was previous waived with the most relevant results from compare against.
                    # Why only before? Consider if you are scanning client-4.3.26-9999. If the you find the 
                    # following waived results:
                    #  client-4.2.6-9999
                    #  client-4.3.25-9999
                    #  client-4.3.26-8888
                    #  client-4.4.1-9999
                    # You can see that 4.3.26-8888 would occur directly before the current NVR. You would not want to
                    # select anything after, because you would find a 4.4 version.
                    
                    # The command below:
                    #                             lists everything starting with ${N}- and then has a digit
                    #                                            includes || true to avoid errors if nothing is found
                    #                                                    adds the current NVR to the echo
                    #                                                              pipes into version sorting
                    #                                                                          greps for the NVR and any line right before it (B1)
                    #                                                                                            Grabs the first line of grep output
                    POSSIBLE_COMPARE=\$(echo -e "`ls ${N}-[0-9]* || true`\n${NVR}" | sort -V | grep ${NVR} -B1 | head -n 1)

                    if [[ "\$POSSIBLE_COMPARE" != "${NVR}" ]]; then
                        # We've found a related, previously waived version.
                        echo "Found previous NVR with waived issues: ${WAIVED_BASE_DIR}/\$POSSIBLE_COMPARE"
                        csdiff ${NVR_SCAN_DIR}/raw_results.js "${WAIVED_BASE_DIR}/\$POSSIBLE_COMPARE/raw_results.js" > ${NVR_SCAN_DIR}/diff_results.js
                    fi
                fi

                cshtml ${NVR_SCAN_DIR}/diff_results.js > ${NVR_SCAN_DIR}/diff_results.html

                # We could read in this into Jenkins, but the files can be >10M, so let jq figure out if there is a diff to review
                if [[ `cat ${NVR_SCAN_DIR}/diff_results.js | jq '.issues | length' -r` != '0' ]]; then
                    echo "Differences detected from previous scan."
                    touch ${NVR_SCAN_DIR}/diff_results.flag
                else
                    rm -f ${NVR_SCAN_DIR}/diff_results.flag
                fi

                # Copy diffs to workspace so we can archive them
                cp ${NVR_SCAN_DIR}/diff_results.* ./cov

                """

                archiveArtifacts(artifacts: "cov/diff_results.*")

                sh """
                set -euxo pipefail
                scp ${NVR_SCAN_DIR}/raw_results.html ocp-build@rcm-guest.app.eng.bos.redhat.com:/mnt/rcm-guest/puddles/RHAOS/coverity/${NVR}.raw_results.html
                scp ${NVR_SCAN_DIR}/diff_results.html ocp-build@rcm-guest.app.eng.bos.redhat.com:/mnt/rcm-guest/puddles/RHAOS/coverity/${NVR}.diff_results.html
                """

                if ( ! fileExists("${NVR_SCAN_DIR}/diff_results.flag") ) {
                    echo "No scan differences detected from last scan. No waivers are required."
                    return // end the stage
                }

                slackChannel.task("Coverity result review: ${NVR}") {
                    taskThread ->

                    taskThread.failure("[NEW SCAN WAIVERS REQUIRED] Please review results for ${NVR}\nDifferences from a previously waived scan: http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/coverity/${NVR}.diff_results.html")

                    commonlib.inputRequired() {
                        happy = false
                        while(!happy) {

                            def raw_results_url = "http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/coverity/${NVR}.raw_results.html"
                            def diff_results_url = "http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/coverity/${NVR}.diff_results.html"
                            echo "Waiver details are required.."

                            prompt = """Coverity has detected new issues during static analysis for ${NVR} .
You must review the findings with an engineering / prodsec resource before waiving these results. If the
findings must be fixed in the code (i.e. not WAIVED), then choose ABORT to stop the pipeline.

Differences from a previously waived scan: ${diff_results_url}
All issues: ${raw_results_url}
"""
                            echo prompt

                            def resp = input message: prompt,
                                submitterParameter: 'approver',
                                parameters: [
                                    [
                                        $class     : 'hudson.model.ChoiceParameterDefinition',
                                        choices    : ['WAIVE', 'ABORT'].join('\n'),
                                        description : 'WAIVE only if an engineering resource has confirmed the findings are NOT a security risk.',
                                        name       : 'action'
                                    ],
                                    string( defaultValue: '',
                                            description: 'Link to slack thread / Jira ticket / etc where the conversation about security concerns was discussed. ',
                                            name: 'conversation_url',
                                            trim: true
                                    ),
                                    text(   defaultValue: '',
                                            description: 'An overview of why these issues were waived. ',
                                            name: 'waiver_overview'
                                    ),
                                ]

                            def action = (resp instanceof String)?resp:resp.action

                            switch(action) {
                            case 'WAIVE':
                                // just fall through
                                break
                            case 'ABORT':
                                error('User chose to abort scan pipeline')
                            }

                            def waiver_details = """
Job: ${env.BUILD_URL}

Approver: ${resp.approver}

Discussion: ${resp.conversation_url}

Overview:\n${resp.waiver_overview}
"""

                            echo "The following waiver details will be recorded >>>>>>>>>>\n${waiver_details}\n<<<<<<<<<<<<"
                            echo "Confirm these details.."

                            def confirm = input message: "Are you completely sure you want to waive using the provided information?",
                                parameters: [
                                    [
                                        $class     : 'hudson.model.ChoiceParameterDefinition',
                                        choices    : ['YES', 'RE-ENTER'].join('\n'),
                                        description : 'If you want to alter your reasons, select RE-ENTER.',
                                        name       : 'action'
                                    ],
                                ]

                            def confim_action = (confirm instanceof String)?confirm:confirm.action

                            if ( confim_action == 'YES' ) {
                                currentBuild.keepLog = true  // Don't ever prune this build
                                happy = true // terminate the waiver input loop
                                writeFile( file: 'waiver.txt', text: waiver_details)

                                archiveArtifacts(artifacts: "waiver.txt")

                                sh """
                                cat waiver.txt > ${NVR_SCAN_DIR}/waiver.txt.`date +%s`
                                # Create the link that will consider this scan's issues waived
                                ln -sfn ${NVR_SCAN_DIR} ${NVR_WAIVED_DIR}
                                """
                            }

                        }

                    }

                }


            }

        }
    }


}
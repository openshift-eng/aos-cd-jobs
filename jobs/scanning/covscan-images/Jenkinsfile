timeout(activity: true, time: 1, unit: 'DAYS') {  // if there is no log activity for 1 day
    node('covscan') {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib
        def slacklib = commonlib.slacklib
        buildlib.kinit()

        properties(
            [
                // A single scan can consume all CPU resources on the node. So don't bother trying to parallelize.
                // If you want to change this, make sure to lock use of the coverity repos so job [1] doesn't update
                // the repo while another job is trying to use it.
                disableConcurrentBuilds(),
                [
                    $class : 'ParametersDefinitionProperty',
                    parameterDefinitions: [
                        commonlib.ocpVersionParam('BUILD_VERSION'),
                        [
                            name: 'IMAGES_FIELD',
                            description: 'How to interpret the IMAGES parameter (IGNORE=Scan all images)',
                            $class: 'hudson.model.ChoiceParameterDefinition',
                            choices: [
                                "IGNORE",
                                "INCLUDE",
                                "EXCLUDE",
                            ].join("\n"),
                            defaultValue: 'Ignore'
                        ],
                        [
                            name: 'IMAGES',
                            description: 'CSV list of images (set IMAGES_FIELD to use).',
                            $class: 'hudson.model.StringParameterDefinition',
                            defaultValue: ""
                        ],
                        commonlib.suppressEmailParam(),
                        [
                            name: 'MAIL_LIST_SUCCESS',
                            description: '(Optional) Success Mailing List',
                            $class: 'hudson.model.StringParameterDefinition',
                            defaultValue: "",
                        ],
                        [
                            name: 'MAIL_LIST_FAILURE',
                            description: 'Failure Mailing List',
                            $class: 'hudson.model.StringParameterDefinition',
                            defaultValue: [
                                'aos-art-automation+failed-custom-build@redhat.com',
                            ].join(',')
                        ],
                        booleanParam(
                            name: 'PRESERVE_BUILDER_IMAGES',
                            defaultValue: false,
                            description: "Do not rebuild parent images if they are available (will save time during testing if true)."
                        ),
                        booleanParam(
                            name: 'IGNORE_WAIVED',
                            defaultValue: false,
                            description: "Do not compute diffs based on waived results (diff will equal all)."
                        ),
                        booleanParam(
                            name: 'FORCE_ANALYSIS',
                            defaultValue: false,
                            description: "Rerun analysis even if results are present for the commit."
                        ),
                        booleanParam(
                            name: 'REBUILD_REPOS',
                            defaultValue: false,
                            description: "Force rebuild of the covscan repositories."
                        ),
                        commonlib.artToolsParam(),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()

        // doozer_working must be in WORKSPACE in order to have artifacts archived
        def doozer_working = "${WORKSPACE}/doozer_working"
        buildlib.cleanWorkdir(doozer_working)

        def group = "openshift-${params.BUILD_VERSION}"
        def doozerOpts = "--working-dir ${doozer_working} --group ${group} "
        def version = params.BUILD_VERSION
        def images = commonlib.cleanCommaList(params.IMAGES)

        timestamps {
            slackChannel = slacklib.to(BUILD_VERSION)
            stage('scan') {
                sshagent(['openshift-bot']) {
                    // To make installing covscan reasonably quick for scanner images, make a local copy of covscan repos.
                    // doozer can use these with the --local-repo arg to images:covscan.
                    withEnv(["https_proxy=", "http_proxy=", "no_proxy="]) {
                        for ( rhel_version in ['7', '8', '9'] ) {
                            prefix = "covscan-rhel-${rhel_version}"
                            repo_fn = "${prefix}.repo"
                            writeFile(file: repo_fn, text: """
[covscan]
name=Copr repo for covscan
baseurl=http://coprbe.devel.redhat.com/repos/kdudka/covscan/epel-${rhel_version}-x86_64/
skip_if_unavailable=True
gpgcheck=0
gpgkey=http://coprbe.devel.redhat.com/repos/kdudka/covscan/pubkey.gpg
enabled=1
enabled_metadata=1

[covscan-testing]
name=Copr repo for covscan-testing
baseurl=http://coprbe.devel.redhat.com/repos/kdudka/covscan-testing/epel-${rhel_version}-x86_64/
skip_if_unavailable=True
gpgcheck=0
gpgkey=http://coprbe.devel.redhat.com/repos/kdudka/covscan-testing/pubkey.gpg
enabled=0
enabled_metadata=1
""")

                            lock('buildvm2-yum') { // Don't use yum while a job like reposync is
                                // download the repo contents and create local repositories
                                if ( params.REBUILD_REPOS ) {
                                    sh "rm -rf ${prefix}_repos /var/tmp/yum-covscan-${rhel_version}"
                                    sh "sudo yum clean metadata"
                                }
                                sh "reposync --cachedir=/var/tmp/yum-covscan-${rhel_version} -c ${repo_fn} -a x86_64 -d -p ${prefix}_repos -n -r covscan -r covscan-testing"
                                sh "createrepo_c ${prefix}_repos/covscan"
                                sh "createrepo_c ${prefix}_repos/covscan-testing"
                            }
                        }
                    }
                    RESULTS_ARCHIVE_DIR = '/mnt/nfs/coverity/results'
                    buildlib.doozer """${doozerOpts}
                        ${params.IMAGES_FIELD=='IGNORE'?'':((params.IMAGES_FIELD=='INCLUDE'?'-i ':'-x ') + images)}
                        images:covscan
                        --local-repo-rhel-7 covscan-rhel-7_repos/covscan
                        --local-repo-rhel-7 covscan-rhel-7_repos/covscan-testing
                        --local-repo-rhel-8 covscan-rhel-8_repos/covscan
                        --local-repo-rhel-8 covscan-rhel-8_repos/covscan-testing
                        --local-repo-rhel-9 covscan-rhel-9_repos/covscan
                        --local-repo-rhel-9 covscan-rhel-9_repos/covscan-testing
                        --result-archive ${RESULTS_ARCHIVE_DIR}
                        --repo-type unsigned
                        ${params.PRESERVE_BUILDER_IMAGES?'--preserve-builder-images':''}
                        ${params.IGNORE_WAIVED?'--ignore-waived':''}
                        ${params.FORCE_ANALYSIS?'--force-analysis':''}
                        "--https-proxy=${env.https_proxy}"
                        --podman-tmpdir=/mnt/jenkins-workspace/podman_tmp/jenkins
                    """
                }
            }

            prodsec_report = []
            stage('waive') {
                archiveArtifacts(artifacts: "doozer_working/*.log")
                def covscan_records = buildlib.parse_record_log(doozer_working)['covscan']

                if ( ! covscan_records ) {
                    error('No covscan records were created by doozer')
                }

                unwaived_count = 0
                for ( int i = 0; i < covscan_records.size(); i++ ) {
                    def record = covscan_records[i]
                    def distgit = record['distgit']
                    def distgit_key = record['distgit_key']
                    def stage_number = record['stage_number']
                    def commit_hash = record['commit_hash']
                    def diff_results_js_path = record['diff_results_js_path']
                    def image_name = record['image']
                    def waive_flag_path = record['waive_path']
                    def commit_results_path = record['commit_results_path']  // local location to store results permanently
                    echo "Checking scan results for ${distgit}"
                    def waived = (record['waived'].equalsIgnoreCase('true'))
                    if ( waived ) {
                        echo "Differences already waived for ${distgit}"
                        continue
                    }

                    // Copy archive results files to spmm-utils (rsync should no-op if it has happened before). This
                    // includes files like all_results.js and diff_results.html.
                    // Paths on spmm-utils are relative to /mnt/rcm-guest. mkdir command is enabled via SSH
                    RCM_RELATIVE_DEST = "puddles/RHAOS/coverity/results/${distgit_key}/${commit_hash}/stage_${stage_number}"
                    commonlib.shell("ssh exd-ocp-buildvm-bot-prod@spmm-util mkdir -p ${RCM_RELATIVE_DEST}")
                    commonlib.shell("rsync -r ${record['commit_results_path']}/ exd-ocp-buildvm-bot-prod@spmm-util:${RCM_RELATIVE_DEST}")

                    def all_results_url = "http://download.eng.bos.redhat.com/rcm-guest/${RCM_RELATIVE_DEST}/all_results.html"
                    def all_results_js_url = "http://download.eng.bos.redhat.com/rcm-guest/${RCM_RELATIVE_DEST}/all_results.js"
                    def diff_results_url = "http://download.eng.bos.redhat.com/rcm-guest/${RCM_RELATIVE_DEST}/diff_results.html"
                    def diff_results_js_url = "http://download.eng.bos.redhat.com/rcm-guest/${RCM_RELATIVE_DEST}/diff_results.js"

                    if ( record['diff_count'] != '0' ) {
                        // Gather the types of issues recorded in the scan
                        unwaived_count++
                        issues = sh(returnStdout: true, script:"cat ${diff_results_js_path} | jq .issues[].checkerName -r | sort | uniq")
                        prodsec_report << [
                                'Image' : image_name,
                                'Build Stage': "${stage_number}",
                                'Distgit': "${distgit} (hash ${commit_hash})",
                                'Unwaived Issue Count': record['diff_count'],
                                'Unwaived Issue Types': issues.split().join(', '),
                                'Unwaived Report': diff_results_url,
                                'Unwaived Raw Data': diff_results_js_url,
                                'Full Issue Count': record['all_count'],
                                'Full Report': all_results_url,
                                'Full Raw Data': all_results_js_url,
                                'Message': 'There are new, unwaived issues',
                        ]

                        echo "Creating ${waive_flag_path} to waive these issues in the future."
                        sh "touch ${waive_flag_path}"  // create flag for future doozer runs
                    } else if ( record['all_count'] != '0' ) {
                        // There are no differences from the last time, but include report on all
                        prodsec_report << [
                                'Image' : image_name,
                                'Build Stage': "${stage_number}",
                                'Distgit': "${distgit} (hash ${commit_hash})",
                                'Unwaived Issue Count': 0,
                                'Full Issue Count': record['all_count'],
                                'Full Report': all_results_url,
                                'Full Raw Data': all_results_js_url,
                                'Message': 'There are no new issues to report from the last scan',
                        ]
                    } else {
                        prodsec_report << [
                                'Image' : image_name,
                                'Build Stage': "${stage_number}",
                                'Distgit': "${distgit} (hash ${commit_hash})",
                                'Full Issue Count': 0,
                                'Message': 'No issues reported by scan',
                        ]
                    }
                }

                prodsec_text = """
    Details of the last OpenShift Coverity Scan:

    Images scanned: ${covscan_records.size()}
    Images with unwaived issues: ${unwaived_count}

    """
                for ( entry in prodsec_report ) {
                    prodsec_text += '\n'
                    entry.each {
                        prodsec_text += "${it.key}: ${it.value}\n"
                    }
                }

                echo "Please send the following report to product security."
                echo "Open a SNOW ticket"
                echo "  Category: Security\n" +
                     "  Topic: Risk Management\n" +
                     "  Assignment Group:  Product Security\n" +
                     "  Impact: 4\n" +
                     "  Urgency: 4\n"

                echo "See archived file prodsec.report.txt"
                writeFile(file: 'prodsec.report.txt', text: prodsec_text)
                archiveArtifacts(artifacts: "prodsec.report.txt")
                echo "prodsec.report.txt content..."
                echo ">>>>>>"
                sh "cat prodsec.report.txt"
                echo "<<<<<<"

            }

        }
    }
}



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
                        name: 'PRESERVE_SCANNER_IMAGES',
                        defaultValue: false,
                        description: "Do not rebuild scanner images if they are available (will save time during testing if true)."
                    ),
                    commonlib.mockParam(),
                ]
            ],
        ]
    )

    commonlib.checkMock()

    GITHUB_BASE = "git@github.com:openshift" // buildlib uses this global var

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
                writeFile(file: 'covscan.repo', text: '''
[covscan]
name=Copr repo for covscan
baseurl=http://coprbe.devel.redhat.com/repos/kdudka/covscan/epel-7-$basearch/
skip_if_unavailable=True
gpgcheck=0
gpgkey=http://coprbe.devel.redhat.com/repos/kdudka/covscan/pubkey.gpg
enabled=1
enabled_metadata=1

[covscan-testing]
name=Copr repo for covscan-testing
baseurl=http://coprbe.devel.redhat.com/repos/kdudka/covscan-testing/epel-7-$basearch/
skip_if_unavailable=True
gpgcheck=0
gpgkey=http://coprbe.devel.redhat.com/repos/kdudka/covscan-testing/pubkey.gpg
enabled=0
enabled_metadata=1
    ''')

                lock('buildvm2-yum') { // Don't use yum while a job like reposync is
                    // download the repo contents and create local repositories
                    sh "reposync  -c covscan.repo -a x86_64 -d -p covscan_repos -n -e covscan_cache -r covscan -r covscan-testing"
                    sh "createrepo covscan_repos/covscan"
                    sh "createrepo covscan_repos/covscan-testing"
                }

                RESULTS_ARCHIVE_DIR = '/mnt/nfs/coverity/results'
                buildlib.doozer """${doozerOpts}
                            ${params.IMAGES_FIELD=='IGNORE'?'':((params.IMAGES_FIELD=='INCLUDE'?'-i ':'-x ') + images)}
                            images:covscan
                            --local-repo covscan_repos/covscan
                            --local-repo covscan_repos/covscan-testing
                            --result-archive ${RESULTS_ARCHIVE_DIR}
                            --repo-type unsigned
                            ${params.PRESERVE_SCANNER_IMAGES?'--preserve-scanner-images':''}
                """
            }
        }

        prodsec_report = []
        stage('waive') {
            archiveArtifacts(artifacts: "doozer_working/*.log")
            def covscan_records = buildlib.parse_record_log(doozer_working)['covscan']
            for ( int i = 0; i < covscan_records.size(); i++ ) {
                def record = covscan_records[i]
                def distgit = record['distgit']
                def distgit_key = record['distgit_key']
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

                // Copy archive results files to rcm-guest (rsync should no-op if it has happened before). This
                // includes files like all_results.js and diff_results.html.
                RCM_RELATIVE_DEST = "rcm-guest/puddles/RHAOS/coverity/results/${distgit_key}/${commit_hash}"
                RCM_GUEST_DEST = "/mnt/${RCM_RELATIVE_DEST}"
                commonlib.shell("ssh ocp-build@rcm-guest.app.eng.bos.redhat.com mkdir -p ${RCM_GUEST_DEST}")
                commonlib.shell("rsync -r ${record['commit_results_path']}/ ocp-build@rcm-guest.app.eng.bos.redhat.com:${RCM_GUEST_DEST}")

                def all_results_url = "http://download.eng.bos.redhat.com/${RCM_RELATIVE_DEST}/all_results.html"
                def all_results_js_url = "http://download.eng.bos.redhat.com/${RCM_RELATIVE_DEST}/all_results.js"
                def diff_results_url = "http://download.eng.bos.redhat.com/${RCM_RELATIVE_DEST}/diff_results.html"
                def diff_results_js_url = "http://download.eng.bos.redhat.com/${RCM_RELATIVE_DEST}/diff_results.js"

                if ( record['diff_count'] != '0' ) {
                    // Gather the types of issues recorded in the scan
                    issues = sh(returnStdout: true, script:"cat ${diff_results_js_path} | jq .issues[].checkerName -r | sort | uniq")
                    prodsec_report << [
                            'Image' : image_name,
                            'Distgit': "${distgit} (hash ${commit_hash})",
                            'Unwaived Issue Count': record['diff_count'],
                            'Unwaived Issue Types': issues.split().join(', '),
                            'Unwaived Report': diff_results_url,
                            'Unwaived Raw Data': diff_results_js_url,
                            'Full Report': all_results_url,
                            'Full Raw Data': all_results_js_url
                    ]

                    echo "Creating ${waive_flag_path} to waive these issues in the future."
                    sh "touch ${waive_flag_path}"  // create flag for future doozer runs
                }
            }

            prodsec_text = """
Details of the last OpenShift Coverity Scan:

Images scanned: ${covscan_records.size()}
Images with unwaived issues: ${prodsec_report.size()}

Unwaived Issue Reports:
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



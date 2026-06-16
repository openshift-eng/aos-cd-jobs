node {
    timestamps {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        commonlib.describeJob("gen-assembly-targeted", """
            <h2>Generate a targeted assembly definition for emergency kernel CVE fixes or RC transitions</h2>
            <p>
            Discovers matching RHCOS and DTK builds for the given kernel NVR(s), then generates an
            assembly definition and opens a pull request against <code>ocp-build-data</code>.
            Supports three use cases:
            <ul>
              <li><b>Kernel CVE fix</b>: provide <code>KERNEL_NVRS</code> to pin kernel + RHCOS + DTK</li>
              <li><b>Image pin</b>: provide only <code>IMAGE_NVRS</code> for RC transitions (e.g. rc.4 &rarr; rc.5)</li>
              <li><b>Both</b>: kernel fix plus additional image pins</li>
            </ul>
            </p>
        """)

        properties(
            [
                disableResume(),
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: "50",
                        daysToKeepStr: "50"
                    )),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.artToolsParam(),
                        commonlib.ocpVersionParam('BUILD_VERSION', '4plus'),
                        string(
                            name: "ASSEMBLY_NAME",
                            description: "The name of the targeted assembly to generate (e.g. 4.21.15 or rc.5)",
                            trim: true
                        ),
                        string(
                            name: "BASIS_ASSEMBLY",
                            description: "The basis assembly to inherit from (e.g. 4.21.14 or rc.4)",
                            trim: true
                        ),
                        string(
                            name: "KERNEL_NVRS",
                            description: "(Optional) Kernel NVR(s) to pin, one per line or comma-separated. Provide one per RHEL target if needed (e.g. kernel-5.14.0-427.125.1.el9_4). Leave empty for image-only assemblies.",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: "BUG_IDS",
                            description: "(Optional) Jira issue IDs to include in issues.include, comma-separated (e.g. OCPBUGS-85292). When provided, sets targeted_fixes_only.",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: "CVE_IDS",
                            description: "(Optional) CVE identifiers for the 'why' text, comma-separated (e.g. CVE-2026-43284).",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: "IMAGE_NVRS",
                            description: "(Optional) Additional image NVR(s) to pin alongside kernel/DTK, one per line or comma-separated (e.g. ose-installer-container-v4.18.0-202502110000.p0.el9).",
                            defaultValue: "",
                            trim: true
                        ),
                        choice(
                            name: "BUILD_SYSTEM",
                            description: "Whether we should look at Brew or Konflux builds",
                            choices: ["konflux", "brew"].join("\n"),
                        ),
                        string(
                            name: "DATE",
                            description: "(Optional) Expected release date. Format: YYYY-Mon-DD or YYYY-MM-DD (e.g. 2026-May-13 or 2026-05-13)",
                            defaultValue: "",
                            trim: true
                        ),
                        string(
                            name: "DOOZER_DATA_PATH",
                            description: "ocp-build-data fork to use (e.g. assembly definition in your own fork)",
                            defaultValue: "https://github.com/openshift-eng/ocp-build-data",
                            trim: true,
                        ),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: false
                        ),
                        booleanParam(
                            name: "TRIGGER_BUILD_SYNC",
                            description: "Automatically trigger build sync against the automatically created PR",
                            defaultValue: true
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()
        stage("initialize") {
            buildlib.registry_quay_dev_login()
            currentBuild.displayName += " - ${params.BUILD_VERSION} - ${params.ASSEMBLY_NAME}"
            if (!params.ASSEMBLY_NAME) {
                error("ASSEMBLY_NAME is required.")
            }
            if (!params.BASIS_ASSEMBLY) {
                error("BASIS_ASSEMBLY is required.")
            }
            if (!params.KERNEL_NVRS && !params.IMAGE_NVRS) {
                error("At least one of KERNEL_NVRS or IMAGE_NVRS must be provided.")
            }
        }

        stage("gen-assembly-targeted") {
            buildlib.cleanWorkdir("./artcd_working")
            sh "mkdir -p ./artcd_working"
            def cmd = [
                "artcd",
                "-v",
                "--working-dir=./artcd_working",
                "--config", "./config/artcd.toml",
            ]

            if (params.DRY_RUN) {
                cmd << "--dry-run"
            }
            cmd += [
                "gen-assembly-targeted",
                "--data-path", params.DOOZER_DATA_PATH,
                "--build-system", params.BUILD_SYSTEM,
                "-g", "openshift-${params.BUILD_VERSION}",
                "--assembly", params.ASSEMBLY_NAME,
                "--basis-assembly", params.BASIS_ASSEMBLY,
            ]
            if (params.KERNEL_NVRS) {
                for (nvr in params.KERNEL_NVRS.split("[,\\n\\s]+")) {
                    nvr = nvr.trim()
                    if (nvr) { cmd += ["--kernel-nvr", nvr] }
                }
            }
            if (params.BUG_IDS) {
                for (bug in params.BUG_IDS.split("[,\\s]+")) {
                    bug = bug.trim()
                    if (bug) { cmd += ["--bug-id", bug] }
                }
            }
            if (params.CVE_IDS) {
                for (cve in params.CVE_IDS.split("[,\\s]+")) {
                    cve = cve.trim()
                    if (cve) { cmd += ["--cve-id", cve] }
                }
            }
            if (params.IMAGE_NVRS) {
                for (nvr in params.IMAGE_NVRS.split("[,\\n\\s]+")) {
                    nvr = nvr.trim()
                    if (nvr) { cmd += ["--image-nvr", nvr] }
                }
            }
            if (params.DATE) {
                cmd += ["--date", params.DATE]
            }
            if (params.TRIGGER_BUILD_SYNC) {
                cmd << "--auto-trigger-build-sync"
            }

            buildlib.withAppCiAsArtPublish() {
                withCredentials([
                    string(credentialsId: "art-bot-slack-token", variable: "SLACK_BOT_TOKEN"),
                    string(credentialsId: "openshift-art-build-bot-app-id", variable: "GITHUB_APP_ID"),
                    file(credentialsId: "openshift-art-build-bot-private-key.pem", variable: "GITHUB_APP_PRIVATE_KEY_PATH"),
                    string(credentialsId: "jenkins-service-account", variable: "JENKINS_SERVICE_ACCOUNT"),
                    string(credentialsId: "jenkins-service-account-token", variable: "JENKINS_SERVICE_ACCOUNT_TOKEN"),
                    file(credentialsId: "konflux-gcp-app-creds-prod", variable: "GOOGLE_APPLICATION_CREDENTIALS"),
                    string(credentialsId: "redis-server-password", variable: "REDIS_SERVER_PASSWORD"),
                    file(credentialsId: "quay-auth-file", variable: "QUAY_AUTH_FILE"),
                ]) {
                    withEnv(["BUILD_URL=${BUILD_URL}"]) {
                        try {
                            commonlib.shell(script: cmd.join(" "))
                        } catch (err) {
                            throw err
                        } finally {
                            commonlib.safeArchiveArtifacts([
                                "artcd_working/**/*.log",
                            ])
                        }
                    }
                }
            }
        }
    }
    }
}

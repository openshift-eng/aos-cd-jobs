@NonCPS
def processImages(lines) {
    def data = []
    lines.split().each { line ->
        // label, name, nvr, version
        def fields = line.split(',')
        if (fields[0] == 'true') {
            data.add([
                name: fields[1],
                nvr: fields[2],
                version: fields[3].replace("v", ""),
                metadata_nvr: fields[2].replace("-operator-container", "-operator-metadata-container"),
            ])
        }
    }
    return data
}


def retrieveBotToken() {
    def token = ""
    withCredentials([usernamePassword(credentialsId: 'quay_appregistry_omps_bot', usernameVariable: 'QUAY_USERNAME', passwordVariable: 'QUAY_PASSWORD')]) {
        def requestJson = """
        {
            "user": {
                "username": "${QUAY_USERNAME}",
                "password": "${QUAY_PASSWORD}"
            }
        }
        """
        retry(3) {
            def response = httpRequest(
                url: "https://quay.io/cnr/api/v1/users/login",
                httpMode: 'POST',
                contentType: 'APPLICATION_JSON',
                requestBody: requestJson,
                timeout: 60,
                validResponseCodes: "200:599",
            )
            if (response.status != 200) {
                sleep(5)
                error "Quay token request failed: ${response.status} ${response.content}"
            }
            token = readJSON(text: response.content).token
        }
    }
    return token
}


node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib

    // Expose properties for a parameterized build
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '')
            ),
            [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    commonlib.ocpVersionParam('BUILD_VERSION', '4'),
                    string(
                        name: 'IMAGES',
                        description: '(Optional) List of images to limit selection (default all)',
                        defaultValue: ""
                    ),
                    [
                        name: 'STREAM',
                        description: 'OMPS appregistry',
                        $class: 'hudson.model.ChoiceParameterDefinition',
                        choices: ['dev', 'stage', 'prod'],
                        defaultValue: 'dev',
                    ],
                    string(
                        name: 'ADVISORY',
                        description: 'Should not be filled if STREAM is "dev"',
                        defaultValue: '',
                    ),
                    booleanParam(
                        name: 'SKIP_PUSH',
                        defaultValue: false,
                        description: "Do not push operator metadata"
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: [
                            'aos-art-automation+failed-appregistry@redhat.com',
                        ].join(',')
                    ),
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    buildlib.initialize(false)

    def workDir = "${env.WORKSPACE}/workDir"
    buildlib.cleanWorkdir(workDir)

    currentBuild.description = "Collecting appregistry images for ${params.BUILD_VERSION}"
    currentBuild.displayName += " - ${params.BUILD_VERSION}"

    // temporarily disable 4.2 pushes until we have figured out what we need to do for them
    def skipPush = (params.BUILD_VERSION == '4.2') ? true : params.SKIP_PUSH

    try {
        def operatorData = []
        sshagent(["openshift-bot"]) {
            stage("fetch appregistry images") {
                def include = params.IMAGES.trim()
                if (include) {
                    include = "--images " + commonlib.cleanCommaList(include)
                }
                def lines = buildlib.doozer """
                    --working-dir ${workDir}
                    --group 'openshift-${params.BUILD_VERSION}'
                    ${include}
                    images:print
                    --label 'com.redhat.delivery.appregistry'
                    --short '{label},{name},{build},{version}'
                """, [capture: true]
                operatorData = processImages(lines)
                writeYaml file: "${workDir}/appreg.yaml", data: operatorData
                currentBuild.description = "appregistry images collected for ${params.BUILD_VERSION}."
            }
            stage("build metadata container") {
                for (def i = 0; i < operatorData.size(); i++) { // @TODO: pass all NVRs simultaneously to doozer
                    def build = operatorData[i]
                    cmd = "operator:metadata ${build.nvr} --merge-branch ${params.STREAM}"
                    buildlib.doozer(cmd)
                }
            }
            stage("push metadata") {
                if (skipPush) {
                    currentBuild.description += "\nskipping metadata push."
                    return
                }
                if (!operatorData) {
                    currentBuild.description += "\nno operator metadata to push."
                    return
                }

                if (params.STREAM == 'dev') {
                    currentBuild.description += "\npushing operator metadata."
                    withCredentials([usernamePassword(credentialsId: 'quay_appregistry_omps_bot', usernameVariable: 'QUAY_USERNAME', passwordVariable: 'QUAY_PASSWORD')]) {
                        def token = retrieveBotToken()
                        for (def i = 0; i < operatorData.size(); i++) {
                            def build = operatorData[i]
                            retry(3) {
                                def response = httpRequest(
                                    url: "https://omps-prod.cloud.paas.upshift.redhat.com/v2/redhat-operators-art/koji/${build.metadata_nvr}",
                                    httpMode: 'POST',
                                    customHeaders: [[name: 'Authorization', value: token]],
                                    timeout: 60,
                                    validResponseCodes: "200:599",
                                )
                                if (response.status != 200) {
                                    sleep(5)
                                    error "OMPS request for ${build.metadata_nvr} failed: ${response.status} ${response.content}"
                                }
                            }
                            currentBuild.description += "\n  ${build.metadata_nvr}"
                        }
                    }
                } else {
                    if (params.ADVISORY) {
                        cmd = """--group openshift-${params.BUILD_VERSION}
                            find-builds -k image
                            --build ${build.metadata_nvr}
                            --attach ${params.ADVISORY}
                        """
                        buildlib.elliott(cmd)
                    }
                }
            }
        }
    } catch (err) {
        currentBuild.description = "Job failed: ${err}\n-----------------\n${currentBuild.description}"
        if (skipPush) { return }  // don't spam on failures we don't care about
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-art-automation@redhat.com",
            replyTo: "aos-team-art@redhat.com",
            subject: "Unexpected error during appregistry job",
            body: "Console output: ${env.BUILD_URL}console\n${currentBuild.description}",
        )

        throw err
    } finally {
        commonlib.safeArchiveArtifacts([
            "workDir/appreg.yaml"
        ])
    }
}

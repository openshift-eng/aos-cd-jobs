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
                    numToKeepStr: '100')
                ),
                [
                $class: 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'BASE_IMAGE_TAGS',
                        description: 'list of openshift cve base images.',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: commonlib.ocpBaseImages.join(' ')
                    ],
                    [
                        name: 'PACKAGE_LIST',
                        description: 'list of packages to update (all if empty).',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: '',
                    ],
                    commonlib.suppressEmailParam(),
                    [
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        $class: 'hudson.model.StringParameterDefinition',
                        defaultValue: 'aos-team-art@redhat.com'
                    ],
                    commonlib.mockParam(),
                ]
            ],
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()
    buildlib.initialize()
    def imageName = params.BASE_IMAGE_TAGS.replaceAll(',', ' ').split()
    def packages = params.PACKAGE_LIST.replaceAll(',', ' ').split()


    currentBuild.displayName = "#${currentBuild.number} Update base images"
    currentBuild.description = ""
    try {
		for(int i = 0; i < imageName.size(); ++i) {
             currentBuild.description += "Built ${imageName[i]}\n"
             commonlib.shell(
                script: "./build.sh ${imageName[i]} ${packages}"
             )
        }
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Unexpected error during CVEs update streams.yml!",
            body: "Encountered an unexpected error while running update base images: ${err}"
        )
        currentBuild.description = "Built ${imageName[i]} error: ${err}\n"

        throw err
    }
}

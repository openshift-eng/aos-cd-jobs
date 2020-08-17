node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("update-base-images", """
        --------------------------------------------------
        Rebuild base images to keep up with published CVEs
        --------------------------------------------------
        Timing: Rebuilds all base container images weekly on Saturday.
        May be run manually for specific updates.

        When RHEL CVEs are released, we do not wait for other teams to update
        base images used somewhere in OCP. For each this job simply runs a
        build that updates the image and gives the update a floating tag which
        is used by product builds.
    """)

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
                    string(
                        name: 'BASE_IMAGE_TAGS',
                        description: 'list of openshift cve base images.',
                        defaultValue: commonlib.ocpBaseImages.join(' ')
                    ),
                    string(
                        name: 'PACKAGE_LIST',
                        description: 'list of packages to update (all if empty).',
                        defaultValue: '',
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: 'aos-team-art@redhat.com'
                    ),
                    commonlib.mockParam(),
                ]
            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )

    commonlib.checkMock()
    buildlib.initialize()
    def imageName = params.BASE_IMAGE_TAGS.replaceAll(',', ' ').split()
    def packages = params.PACKAGE_LIST.replaceAll(',', ' ')


    currentBuild.displayName = "#${currentBuild.number} Update base images"
    currentBuild.description = ""
    try {
        imageTasks = imageName.collectEntries { name -> [name,
            { ->
                 lock("base-image-distgit") {  // cannot all update same distgit at same time
                     result = commonlib.shell(
                        script: "./distgit.sh ${name} ${packages}",
                        returnAll: true,
                     )
                 }
                 // but after update, all can build at the same time.

                 if (result.returnStatus != 0) {
                    // if rebase failed, mark as partially failed (others still run)
                    currentBuild.result = 'UNSTABLE'
                    currentBuild.description += "FAILED distgit: ${name}\n"
                    return
                 }

                 currentBuild.description += "Build ${name}\n"
                 def url = result.stdout.readLines()[-1]
                 def rc = commonlib.shell(
                    script: "cd build-${name} && rhpkg --user=ocp-build container-build --repo-url '${url}'",
                    returnStatus: true,
                 )

                 if (rc != 0) {
                    currentBuild.result = 'UNSTABLE'
                    currentBuild.description += "FAILED build: ${name}\n"
                 }
            }
        ]}
        parallel imageTasks
    } catch (err) {
        commonlib.email(
            to: "${params.MAIL_LIST_FAILURE}",
            from: "aos-team-art@redhat.com",
            subject: "Unexpected error during CVEs update streams.yml!",
            body: "Encountered an unexpected error while running update base images: ${err}"
        )
        currentBuild.description += "ERROR: ${err}\n"

        throw err
    }
}

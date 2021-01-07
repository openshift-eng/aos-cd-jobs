node {
    checkout scm
    def buildlib = load("pipeline-scripts/buildlib.groovy")
    def commonlib = buildlib.commonlib
    commonlib.describeJob("update-base-images", """
        <h2>Rebuild base images to keep up with published CVEs</h2>
        <b>Timing</b>: Rebuilds all base container images weekly on Saturday.
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
                        defaultValue: commonlib.ocpBaseImages.join(' '),
                        trim: true,
                    ),
                    string(
                        name: 'PACKAGE_LIST',
                        description: 'list of packages to update (all if empty).',
                        defaultValue: '',
                        trim: true,
                    ),
                    commonlib.suppressEmailParam(),
                    string(
                        name: 'MAIL_LIST_FAILURE',
                        description: 'Failure Mailing List',
                        defaultValue: 'aos-team-art@redhat.com',
                        trim: true,
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
    red_p = '<p style="color:#f00">'
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
                    currentBuild.description += "${red_p}FAILED distgit: ${name}</p>"
                    return
                 }

                 currentBuild.description += "<br/>Build ${name}"
                 def url = result.stdout.readLines()[-1]
                 def rc = commonlib.shell(
                    script: "cd build-${name} && rhpkg --user=ocp-build container-build --repo-url '${url}'",
                    returnStatus: true,
                 )

                 if (rc != 0) {
                    currentBuild.result = 'UNSTABLE'
                    currentBuild.description += "${red_p}FAILED build: ${name}</p>"
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
        currentBuild.description += "${red_p}ERROR: ${err}</p>"

        throw err
    } finally {
        buildlib.cleanWorkspace()
    }
}

#!/usr/bin/env groovy

import java.text.SimpleDateFormat

node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def buildlib = load("pipeline-scripts/buildlib.groovy")
        def commonlib = buildlib.commonlib

        def dateFormat = new SimpleDateFormat("yyyy-MMM-dd")
        def date = new Date()

        // Expose properties for a parameterized build
        properties(
            [
                buildDiscarder(
                    logRotator(
                        artifactDaysToKeepStr: "",
                        artifactNumToKeepStr: "",
                        daysToKeepStr: "",
                        numToKeepStr: "")),
                [
                    $class: "ParametersDefinitionProperty",
                    parameterDefinitions: [
                        commonlib.ocpVersionParam("VERSION"),
                        booleanParam(
                            name: "ENABLE_AUTOMATION",
                            description: "Unfreeze automation to enable building and sweeping into the new advisories",
                            defaultValue: true
                        ),
                        string(
                            name: "ASSIGNED_TO",
                            description: "Advisories are assigned to QE",
                            defaultValue: "openshift-qe-errata@redhat.com"
                        ),
                        string(
                            name: "MANAGER",
                            description: "ART team manager (not release manager)",
                            defaultValue: "vlaad@redhat.com"
                        ),
                        string(
                            name: "PACKAGE_OWNER",
                            description: "Must be an individual email address; may be anyone who wants random advisory spam",
                            defaultValue: "lmeyer@redhat.com"
                        ),
                        choice(
                            name: "IMPETUS",
                            description: "For which reason are the advisories being created",
                            choices: [
                                "standard",
                                "cve",
                                "ga",
                                "test",
                            ].join("\n"),
                        ),
                        string(
                            name: "DATE",
                            description: "Intended release date. Format: YYYY-Mon-dd (i.e.: 2050-Jan-01)",
                            defaultValue: "${dateFormat.format(date)}"
                        ),
                        booleanParam(
                            name: "DRY_RUN",
                            description: "Take no action, just echo what the job would have done.",
                            defaultValue: false
                        ),
                        commonlib.suppressEmailParam(),
                        string(
                            name: "MAIL_LIST_FAILURE",
                            description: "Failure Mailing List",
                            defaultValue: [
                                "aos-art-automation+failed-ocp4-build@redhat.com"
                            ].join(",")
                        ),
                        text(
                            name: "SPECIAL_NOTES",
                            description: "(Optional) special notes to include in the email",
                            defaultValue: ""
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )

        commonlib.checkMock()

        currentBuild.description = ""
        try {
            stage("kinit") {
                buildlib = load("pipeline-scripts/buildlib.groovy")
                buildlib.kinit()
            }
            stage("create rpm advisory") {
                cmd = """
                    -g openshift-${params.VERSION}
                    create -k rpm
                    --assigned-to ${params.ASSIGNED_TO}
                    --manager ${params.MANAGER}
                    --package-owner ${params.PACKAGE_OWNER}
                    --impetus ${params.IMPETUS}
                    ${params.DATE ? "--date ${params.DATE} " : ""}
                    ${params.DRY_RUN ? "" : "--yes"}
                """

                echo "elliott cmd: ${cmd}"
                out = buildlib.elliott(cmd, [capture: true])
                echo "out: ${out}"

                rpm_advisory_id = buildlib.extractAdvisoryId(out)
                echo "extracted rpm_advisory_id: ${rpm_advisory_id}"
            }
            stage("create image advisory") {
                cmd = """
                    -g openshift-${params.VERSION}
                    create -k image
                    --assigned-to ${params.ASSIGNED_TO}
                    --manager ${params.MANAGER}
                    --package-owner ${params.PACKAGE_OWNER}
                    --impetus ${params.IMPETUS}
                    ${params.DATE ? "--date ${params.DATE} " : ""}
                    ${params.DRY_RUN ? "" : "--yes"}
                """

                echo "elliott cmd: ${cmd}"
                out = buildlib.elliott(cmd, [capture: true])
                echo "out: ${out}"

                image_advisory_id = buildlib.extractAdvisoryId(out)
                echo "extracted image_advisory_id: ${image_advisory_id}"
            }
            stage("create Extras advisory") {
                if (params.VERSION.startsWith("4")) {
                    cmd = """
                        -g openshift-${params.VERSION}
                        create -k image
                        --assigned-to ${params.ASSIGNED_TO}
                        --manager ${params.MANAGER}
                        --package-owner ${params.PACKAGE_OWNER}
                        --impetus extras
                        ${params.DATE ? "--date ${params.DATE} " : ""}
                        ${params.DRY_RUN ? "" : "--yes"}
                    """

                    echo "elliott cmd: ${cmd}"
                    out = buildlib.elliott(cmd, [capture: true])
                    echo "out: ${out}"

                    extras_advisory_id = buildlib.extractAdvisoryId(out)
                    echo "extracted extras_advisory_id: ${extras_advisory_id}"
                }
            }
            stage("create OLM Operators metadata advisory") {
                if (params.VERSION.startsWith("4")) {
                    cmd = """
                        -g openshift-${params.VERSION}
                        create -k image
                        --assigned-to ${params.ASSIGNED_TO}
                        --manager ${params.MANAGER}
                        --package-owner ${params.PACKAGE_OWNER}
                        --impetus metadata
                        ${params.DATE ? "--date ${params.DATE} " : ""}
                        ${params.DRY_RUN ? "" : "--yes"}
                    """

                    echo "elliott cmd: ${cmd}"
                    out = buildlib.elliott(cmd, [capture: true])
                    echo "out: ${out}"

                    metadata_advisory_id = buildlib.extractAdvisoryId(out)
                    echo "extracted metadata_advisory_id: ${metadata_advisory_id}"
                }
            }
            stage("update job description with advisory links") {
                currentBuild.displayName = "${params.VERSION}.z advisories${params.DRY_RUN ? " [DRY_RUN]" : ""}"
                currentBuild.description = """
                    RPM: https://errata.devel.redhat.com/advisory/${rpm_advisory_id}\n
                    Image: https://errata.devel.redhat.com/advisory/${image_advisory_id}\n
                """
                if (params.VERSION.startsWith("4")) {
                    currentBuild.description += """
                        Extras: https://errata.devel.redhat.com/advisory/${extras_advisory_id}\n
                        OLM Operators metadata: https://errata.devel.redhat.com/advisory/${metadata_advisory_id}\n
                    """
                }
            }
            sshagent(["openshift-bot"]) {
                stage("commit new advisories to ocp-build-data") {
                    cmd = """
                        rm -rf ocp-build-data ;
                        git clone --single-branch --branch openshift-${params.VERSION} git@github.com:openshift/ocp-build-data.git ;
                        cd ocp-build-data ;
                        sed -E -e 's/^  image: [0-9]+\$/  image: ${image_advisory_id}/' -e 's/^  rpm: [0-9]+\$/  rpm: ${rpm_advisory_id}/' -i group.yml ;
                    """
                    if (params.VERSION.startsWith("4")) {
                        cmd += """
                            sed -E -e 's/^  extras: [0-9]+\$/  extras: ${extras_advisory_id}/' \
                                   -e 's/^  metadata:  [0-9]+\$/  metadata: ${metadata_advisory_id}/' \
                            -i group.yml ;
                        """
                    }
                    if (params.ENABLE_AUTOMATION) {
                        cmd += "sed -e 's/freeze_automation:.*/freeze_automation: no/' -i group.yml ; "
                    }
                    cmd += """
                        git diff ;
                        git add . ;
                        git commit -m 'Update advisories on group.yml' ;
                        git push origin openshift-${params.VERSION}
                    """

                    echo "shell cmd: ${cmd}"
                    if (params.DRY_RUN) {
                        out = "DRY RUN mode, command did not run"
                    } else {
                        out = commonlib.shell(
                            returnStdout: true,
                            script: cmd
                        )
                    }
                    echo "out: ${out}"
                }
            }
            stage("add placeholder bugs to advisories") {
                kind = params.VERSION.startsWith("3") ? "image" : "rpm"

                cmd = "-g openshift-${params.VERSION} "
                cmd+= "create-placeholder "
                cmd+= "--kind ${kind} "
                cmd+= "--use-default-advisory ${kind}"

                echo "elliott cmd: ${cmd}"
                if (params.DRY_RUN) {
                    out = "DRY RUN mode, command did not run"
                } else {
                    out = buildlib.elliott(cmd, [capture: true])
                }
                echo "out: ${out}"

                // Extras placeholder
                if (params.VERSION.startsWith("4")) {
                    cmd = """
                        -g openshift-${params.VERSION}
                        create-placeholder
                        --kind extras
                        --use-default-advisory extras
                    """

                    echo "elliott cmd: ${cmd}"
                    if (params.DRY_RUN) {
                        out = "DRY RUN mode, command did not run"
                    } else {
                        out = buildlib.elliott(cmd, [capture: true])
                    }
                    echo "out: ${out}"
                }

                // OLM Operators metadata placeholder
                if (params.VERSION.startsWith("4")) {
                    cmd = """
                        -g openshift-${params.VERSION}
                        create-placeholder
                        --kind metadata
                        --use-default-advisory metadata
                    """

                    echo "elliott cmd: ${cmd}"
                    if (params.DRY_RUN) {
                        out = "DRY RUN mode, command did not run"
                    } else {
                        out = buildlib.elliott(cmd, [capture: true])
                    }
                    echo "out: ${out}"
                }
            }
        } catch (err) {
            currentBuild.description += "\n-----------------\n\n${err}"
            currentBuild.result = "FAILURE"

            if (params.MAIL_LIST_FAILURE.trim()) {
                commonlib.email(
                    to: params.MAIL_LIST_FAILURE,
                    from: "aos-team-art@redhat.com",
                    subject: "Error building OCP ${params.BUILD_VERSION}",
                    body:
                    """\
    Pipeline build "${currentBuild.displayName}" encountered an error:
    ${currentBuild.description}


    View the build artifacts and console output on Jenkins:
    - Jenkins job: ${env.BUILD_URL}
    - Console output: ${env.BUILD_URL}console

    """
                )
            }
            throw err  // gets us a stack trace FWIW
        }
    }
}

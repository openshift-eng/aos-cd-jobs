#!/usr/bin/env groovy

import java.text.SimpleDateFormat

node {
    wrap([$class: "BuildUser"]) {
        checkout scm
        def lib = load("advisories.groovy")
        def buildlib = lib.buildlib
        def commonlib = lib.commonlib
        def slacklib = commonlib.slacklib

        def dateFormat = new SimpleDateFormat("yyyy-MMM-dd")
        def date = new Date()

        commonlib.describeJob("advisories", """
            <h2>Create the standard advisories for a new release</h2>
            <b>Timing</b>: The "release" job runs this as soon as the previous release
            for this version is defined in the release-controller.

            For more details see the <a href="https://github.com/openshift/aos-cd-jobs/blob/master/jobs/build/advisories/README.md" target="_blank">README</a>
        """)

        // Please update README.md if modifying parameter names or semantics
        properties(
            [
                disableResume(),
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
                            name: "REQUEST_LIVE_IDs",
                            description: "(No effect once SUPPRESS_EMAIL is checked) Sending emails request live ids to docs team once advisories are created",
                            defaultValue: true
                        ),
                        string(
                            name: "ASSIGNED_TO",
                            description: "Advisories are assigned to QE",
                            defaultValue: "openshift-qe-errata@redhat.com",
                            trim: true
                        ),
                        string(
                            name: "MANAGER",
                            description: "ART team manager (not release manager)",
                            defaultValue: "vlaad@redhat.com",
                            trim: true
                        ),
                        string(
                            name: "PACKAGE_OWNER",
                            description: "Must be an individual email address; may be anyone who wants random advisory spam",
                            defaultValue: "lmeyer@redhat.com",
                            trim: true
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
                            description: "Intended release date. Format: YYYY-Mon-dd (example: 2050-Jan-01)",
                            defaultValue: "${dateFormat.format(date)}",
                            trim: true
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
                            ].join(","),
                            trim: true
                        ),
                        string(
                            name: 'LIVE_ID_MAIL_LIST',
                            description: 'Current default is OpenShift CCS Mailing List and OpenShift ART',
                            defaultValue: [
                                "openshift-ccs@redhat.com",
                                "aos-team-art@redhat.com"
                            ].join(","),
                            trim: true
                        ),
                        booleanParam(
                            name: 'TEXT_ONLY',
                            description: 'Create one text only advisory, the following params should modified manually ref this doc https://docs.google.com/document/d/1f2nhs2u59G_iyd3JI_IJq9C2rvM1z5vjWTLE133oToI if this is true',
                            defaultValue: false,
                        ),
                        text(
                            name: 'SYNOPIS',
                            description: 'Synopsis value for text only advisory',
                            defaultValue: "OpenShift Container Platform 4.7.z notification of delayed upgrade path to 4.8"
                        ),
                        text(
                            name: 'TOPIC',
                            description: 'Topic value for text only advisory',
                            defaultValue: "Upgrading from Red Hat OpenShift Container Platform version 4.7.z to version 4.8 is not currently available."
                        ),
                        text(
                            name: 'DESCRIPTION',
                            description: 'Description value for text only advisory',
                            defaultValue: '''Red Hat has discovered an issue in OpenShift Container Platform 4.7.17 that provides sufficient cause for Red Hat to not support installations of, or upgrades to, version 4.7.17:

https://bugzilla.redhat.com/show_bug.cgi?id=1973006

For more information, see https://access.redhat.com/solutions/6131081

The delayed availability of this upgrade path does not affect the support of clusters as documented in the OpenShift Container Platform version life cycle policy, and Red Hat will provide supported update paths as soon as possible.

You can view the OpenShift Container Platform life cycle policy at https://access.redhat.com/support/policy/updates/openshift

For more information about upgrade paths and recommendations, see https://docs.openshift.com/container-platform/4.6/updating/updating-cluster-between-minor.html#upgrade-version-paths
                                           ''',
                        ),
                        text(
                            name: 'SOLUTION',
                            description: 'Solution value for text only advisory',
                            defaultValue: '''eneral Guidance:
                            
All OpenShift Container Platform 4.6 users are advised to upgrade to the next version when it is available in the appropriate release channel. To check for currently recommended updates, use the OpenShift Console or the CLI oc command.

Outside of a cluster, view the currently recommended upgrade paths with the Red Hat OpenShift Container Platform Update Graph tool

https://access.redhat.com/labs/ocpupgradegraph/update_channel

Instructions for upgrading a cluster are available at https://docs.openshift.com/container-platform/4.6/updating/updating-cluster-between-minor.html#understanding-upgrade-channels_updating-cluster-between-minor
                                          ''',
                        ),
                        text(
                            name: 'BUGTITLE',
                            description: 'Bug title value for the bug used in text only advisory',
                            defaultValue: "No upgrade edge available from 4.6.32 to 4.7"
                        ),
                        text(
                            name: 'BUGDESCRIPTION',
                            description: 'Bug description value for the bug used in text only advisory',
                            defaultValue: '''Description of problem:
                            
Upgrading from Red Hat OpenShift Container Platform version 4.7.z to version 4.8 is not currently available.

Customers would have to upgrade to 4.7.z or later to upgrade to 4.8 version.
                                          ''',
                        ),
                        commonlib.mockParam(),
                    ]
                ],
            ]
        )   // Please update README.md if modifying parameter names or semantics

        commonlib.checkMock()

        currentBuild.displayName = "${params.VERSION}.z advisories${params.DRY_RUN ? " [DRY_RUN]" : ""}"
        currentBuild.description = ""
        def (major, minor) = commonlib.extractMajorMinorVersionNumbers(params.VERSION)

        try {
            stage("kinit") {
                buildlib.kinit()
            }
            stage("create advisories") {
                if (params.TEXT_ONLY) {
                    lib.create_textonly()
                } else {
                    lib.create_advisory("image")
                    lib.create_advisory("rpm")
                    if (major > 3) {
                        lib.create_advisory("extras")
                        lib.create_advisory("metadata")
                    }
                }
            }

            stage("sending email to request Live IDs") {
                if (params.REQUEST_LIVE_IDs) {
                    def main_advisory = (major == 3) ? "rpm" : "image"
                    def draft = [
                        "Hello docs team, ART would like to request Live IDs for our ${params.VERSION}.z advisories:",
                        "${main_advisory}: https://errata.devel.redhat.com/advisory/${lib.ADVISORIES[main_advisory]}",
                        "",
                        "This is the current set of advisories we intend to ship:"
                    ]
                    lib.ADVISORIES.each {
                        draft << "- ${it.key}: https://errata.devel.redhat.com/advisory/${it.value}"
                    }
                    body = draft.join('\n')
                    if (params.DRY_RUN) {
                        out = "DRY RUN mode, email did not send to ${params.LIVE_ID_MAIL_LIST}\n\n subject: Live IDs for ${params.VERSION}\n\n body: ${body}"
                        echo "out: ${out}"
                    } else {
                        commonlib.email(
                            to: "${params.LIVE_ID_MAIL_LIST}",
                            from: "aos-art-automation@redhat.com",
                            subject: "Live IDs for ${params.VERSION}",
                            body: "${body}"
                        );
                    }
                }
            }
            sshagent(["openshift-bot"]) {
                stage("commit new advisories to ocp-build-data") {
                    if (params.TEXT_ONLY != true) {
                        def edit = [
                            "rm -rf ocp-build-data",
                            "git clone --single-branch --branch openshift-${params.VERSION} git@github.com:openshift/ocp-build-data.git",
                            "cd ocp-build-data"
                        ]
                        for (advisory in lib.ADVISORIES) {
                            edit << "sed -Ei 's/^  ${advisory.key}: [0-9]+\$/  ${advisory.key}: ${advisory.value}/' group.yml"
                        }
                        commit = [
                            "git diff",
                            "git add .",
                            "git commit -m 'Update advisories on group.yml'",
                            "git push origin openshift-${params.VERSION}",
                        ]

                        cmd = (edit << commit).flatten().join('\n')

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
                    } else {
                        echo "skip commit text only advisory to ocp-build-data"
                    }
                }
            }

            stage("add placeholder bugs to advisories") {
                if (params.TEXT_ONLY != true) {
                    lib.ADVISORIES.each {
                        if (it.key == "rpm" && major == 3) { return }
                        if (it.key == "image" && major > 3) { return }
                        if (it.key.contains('rhsa')) { return }
                        lib.create_placeholder(it.key)
                    }
                }
            }

            stage("slack notification to release channel") {
                slacklib.to(params.VERSION).say("""
                *:white_check_mark: New advisories created:*
                ${currentBuild.description}

                buildvm job: ${commonlib.buildURL('console')}
                """)
            }

        } catch (err) {
            currentBuild.description += "<hr>${err}"
            currentBuild.result = "FAILURE"

            slacklib.to(params.VERSION).say("""
            *:heavy_exclamation_mark: advisories creation failed*
            buildvm job: ${commonlib.buildURL('console')}
            """)

            if (params.MAIL_LIST_FAILURE.trim()) {
                commonlib.email(
                    to: params.MAIL_LIST_FAILURE,
                    from: "aos-team-art@redhat.com",
                    subject: "Error building OCP ${params.BUILD_VERSION}",
                    body:
                    """\
    Pipeline build "${currentBuild.displayName}" encountered an error:
    ${err}


    View the build artifacts and console output on Jenkins:
    - Jenkins job: ${env.BUILD_URL}
    - Console output: ${env.BUILD_URL}console

    """
                )
            }
            throw err  // gets us a stack trace FWIW
        } finally {
            buildlib.cleanWorkspace()
        }
    }
}

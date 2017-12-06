#!/usr/bin/env groovy

// Expose properties for a parameterized build
properties(
        [
            buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '1000')),
            [$class : 'ParametersDefinitionProperty',
          parameterDefinitions:
                  [
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'openshift-build-1', description: 'Jenkins agent node', name: 'TARGET_NODE'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "git@github.com:openshift\ngit@github.com:jupierce\ngit@github.com:jupierce-aos-cd-bot\ngit@github.com:adammhaile-aos-cd-bot", defaultValue: 'git@github.com:openshift', description: 'Github base for repos', name: 'GITHUB_BASE'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "openshift-bot\naos-cd-test\njupierce-aos-cd-bot\nadammhaile-aos-cd-bot", defaultValue: 'aos-cd-test', description: 'SSH credential id to use', name: 'SSH_KEY_ID'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "3.9\n3.8\n3.7\n3.6\n3.5\n3.4\n3.3", defaultValue: '3.9', description: 'OCP Version to build', name: 'BUILD_VERSION'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-cicd@redhat.com, aos-qe@redhat.com,jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                          [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Enable intra-day build hack for CL team CI?', name: 'EARLY_LATEST_HACK'],
                          [$class: 'hudson.model.ChoiceParameterDefinition', choices: "release\npre-release\nonline:int\nonline:stg", description:
'''
release                   {ose,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>
pre-release               {origin,origin-web-console,openshift-ansible}/release-X.Y ->  https://mirror.openshift.com/enterprise/enterprise-X.Y/latest/<br>
online:int                {origin,origin-web-console,openshift-ansible}/master -> online-int yum repo<br>
online:stg                {origin,origin-web-console,openshift-ansible}/stage -> online-stg yum repo<br>
''', name: 'BUILD_MODE'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Sign RPMs with openshifthosted?', name: 'SIGN'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Mock run to pickup new Jenkins parameters?', name: 'MOCK'],
                          [$class: 'hudson.model.BooleanParameterDefinition', defaultValue: false, description: 'Run as much code as possible without pushing / building?', name: 'TEST'],
                          [$class: 'hudson.model.TextParameterDefinition', defaultValue: "", description: 'Include special notes in the build email?', name: 'SPECIAL_NOTES'],
                  ]
            ],
            disableConcurrentBuilds()
        ]
)

IS_TEST_MODE = TEST.toBoolean()
BUILD_VERSION_MAJOR = BUILD_VERSION.tokenize('.')[0].toInteger() // Store the "X" in X.Y
BUILD_VERSION_MINOR = BUILD_VERSION.tokenize('.')[1].toInteger() // Store the "Y" in X.Y
SIGN_RPMS = SIGN.toBoolean()

def mail_success( version ) {

    def target = "(Release Candidate)"
    def mirrorURL = "https://mirror.openshift.com/enterprise/enterprise-${version.substring(0,3)}"

    if ( BUILD_MODE == "online:int" ) {
        target = "(Integration Testing)"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-int"
    }

    if ( BUILD_MODE == "online:stg" ) {
        target = "(Stage Testing)"
        mirrorURL = "https://mirror.openshift.com/enterprise/online-stg"
    }

    def inject_notes = ""
    if ( SPECIAL_NOTES.trim() != "" ) {
        inject_notes = "\n***Special notes associated with this build****\n${SPECIAL_NOTES.trim()}\n***********************************************\n"
    }

    mail(
            to: "${MAIL_LIST_SUCCESS}",
            from: "aos-cd@redhat.com",
            replyTo: 'smunilla@redhat.com',
            subject: "[aos-cicd] New build for OpenShift ${target}: ${version}",
            body: """\
OpenShift Version: v${version}
${inject_notes}
Puddle (internal): http://download-node-02.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/AtomicOpenShift/${version.substring(0,3)}/${OCP_PUDDLE}
  - Mirror: ${mirrorURL}/${OCP_PUDDLE}
  - Images have been built for this puddle
  - Images have been pushed to registry.reg-aws.openshift.com:443     (Get pull acceess [1])
  [1] https://github.com/openshift/ops-sop/blob/master/services/opsregistry.asciidoc#using-the-registry-manually-using-rh-sso-user

Brew:
  - Openshift: ${OSE_BREW_URL}
  - OpenShift Ansible: ${OA_BREW_URL}

Jenkins job: ${env.BUILD_URL}


Are your Atomic OpenShift changes in this build? Check here:
https://github.com/openshift/ose/commits/v${NEW_VERSION}-${NEW_RELEASE}/

===Atomic OpenShift changelog snippet===
${OSE_CHANGELOG}


Are your OpenShift Ansible changes in this build? Check here:
https://github.com/openshift/openshift-ansible/commits/openshift-ansible-${NEW_VERSION}-${NEW_RELEASE}/

===OpenShift Ansible changelog snippet===
${OA_CHANGELOG}
""");

    try {
            timeout(3) {
                sendCIMessage( messageContent: "New build for OpenShift ${target}: ${version}",
                        messageProperties: """build_mode=${BUILD_MODE}
mirror_url=${mirrorURL}
image_registry_root=registry.reg-aws.openshift.com:443
brew_task_url_openshift=${OSE_BREW_URL}
brew_task_url_openshift_ansible=${OA_BREW_URL}
""",
                        messageType: 'ComponentBuildDone',
                        overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
                        providerName: 'CI Red Hat UMB'
                )
            }
    } catch ( mex ) {
            echo "Error while sending CI message: ${mex}"
    }
}

// Will be used to track which atomic-openshift build was tagged before we ran.
PREV_BUILD = null

node(TARGET_NODE) {

    checkout scm
    AOS_CD_JOBS_COMMIT_SHA = sh(
            returnStdout: true,
            script: "git rev-parse HEAD",
    ).trim()
        
    try{
            // Clean up old images so that we don't run out of device mapper space
            sh "docker rmi --force \$(docker images  | grep v${BUILD_VERSION} | awk '{print \$3}')"
    } catch ( cce ) {
            echo "Error cleaning up old images: ${cce}"
    }

    PUDDLE_CONF_BASE="https://raw.githubusercontent.com/openshift/aos-cd-jobs/${AOS_CD_JOBS_COMMIT_SHA}/build-scripts/puddle-conf"
    PUDDLE_CONF="${PUDDLE_CONF_BASE}/atomic_openshift-${BUILD_VERSION}.conf"
    PUDDLE_SIGN_KEYS = SIGN_RPMS?"b906ba72":null

    def commonlib = load( "pipeline-scripts/commonlib.groovy")
    commonlib.initialize()

    def buildlib = load( "pipeline-scripts/buildlib.groovy")
    buildlib.initialize()
    echo "Initializing build: #${currentBuild.number} - ${BUILD_VERSION}.?? (${BUILD_MODE})"

    // oit_working must be in WORKSPACE in order to have artifacts archived
    OIT_WORKING = "${WORKSPACE}/oit_working"
    //Clear out previous work
    sh "rm -rf ${OIT_WORKING}"
    sh "mkdir -p ${OIT_WORKING}"

    try {
        sshagent([SSH_KEY_ID]) { // To work on real repos, buildlib operations must run with the permissions of openshift-bot

        PREV_BUILD = sh(returnStdout: true, script: "brew latest-build --quiet rhaos-${BUILD_VERSION}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()

        stage( "enterprise-images repo" ) {
            buildlib.initialize_enterprise_images_dir()
        }

        stage( "ose repo" ) {
            master_spec = buildlib.initialize_ose()
            // If the target version resides in ose#master
            IS_SOURCE_IN_MASTER = ( BUILD_VERSION == master_spec.major_minor )
        }

        stage( "openshift-jenkins repo ") {
          buildlib.initialize_openshift_jenkins()

          JENKINS_SOURCE_BRANCH = "master"
          dir( OPENSHIFT_JENKINS_DIR ) {
              if ( ! IS_SOURCE_IN_MASTER ) {
                  if(BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR >= 6 ){
                      JENKINS_SOURCE_BRANCH = "openshift-${BUILD_VERSION_MAJOR}.${BUILD_VERSION_MINOR}"
                  }
              }
              sh "git checkout ${JENKINS_SOURCE_BRANCH}"
          }
        }

        stage( "origin-web-console repo" ) {
            sh "go get github.com/jteeuwen/go-bindata"
            buildlib.initialize_origin_web_console()
            dir( WEB_CONSOLE_DIR ) {
                // Enable fake merge driver used in our .gitattributes
                sh "git config merge.ours.driver true"
                // Use fake merge driver on specific directories
                // We will be re-generating the dist directory, so ignore it for the merge
                sh "echo 'dist/** merge=ours' >> .gitattributes"
            }
        }

        stage( "openshift-ansible repo" ) {
            buildlib.initialize_openshift_ansible()
        }

        stage( "analyze" ) {
            dir ( env.OSE_DIR ) {

                if ( IS_SOURCE_IN_MASTER ) {
                    if ( BUILD_MODE == "release" ) {
                        error( "You cannot build a release while it resides in master; cut an enterprise branch" )
                    }
                } else {
                    if ( BUILD_MODE != "release" && BUILD_MODE != "pre-release" ) {
                        error( "Invalid build mode for a release that does not reside in master: ${BUILD_MODE}" )
                    }
                }

                if ( IS_SOURCE_IN_MASTER ) {
                    if ( BUILD_MODE == "online:stg" ) {
                        OSE_SOURCE_BRANCH = "stage"
                        UPSTREAM_SOURCE_BRANCH = "upstream/stage"
                        sh "git checkout -b stage origin/stage"
                    } else {
                        OSE_SOURCE_BRANCH = "master"
                        UPSTREAM_SOURCE_BRANCH = "upstream/master"
                    }
                } else {
                    OSE_SOURCE_BRANCH = "enterprise-${BUILD_VERSION}"
                    if ( BUILD_MODE == "release" ) {
                        // When building in release mode, no longer pull from upstream
                        UPSTREAM_SOURCE_BRANCH = null
                    } else {
                        UPSTREAM_SOURCE_BRANCH = "upstream/release-${BUILD_VERSION}"
                    }
                    // Create the non-master source branch and have it track the origin ose repo
                    sh "git checkout -b ${OSE_SOURCE_BRANCH} origin/${OSE_SOURCE_BRANCH}"
                }

                echo "Building from ose branch: ${OSE_SOURCE_BRANCH}"

                spec = buildlib.read_spec_info("origin.spec")
                rel_fields = spec.release.tokenize(".")


                if ( BUILD_MODE == "online:int" || BUILD_MODE == "online:stg" ) {
                    /**
                     * In non-release candidates, we need the following fields
                     *      REL.INT.STG
                     * REL = 0    means pre-release,  1 means release
                     * INT = fields used to differentiate online:int builds
                     * STG = fields used to differentiate online:stg builds
                     */

                    while ( rel_fields.size() < 3 ) {
                        rel_fields << "0"    // Ensure there are enough fields in the array
                    }

                    if ( rel_fields[0].toInteger() != 0 ) {
                        // Don't build release candidate images this way since they can't wind up
                        // in registry.access with a tag OCP can pull.
                        error( "Do not build released products in ${BUILD_MODE}; just build in release or pre-release mode" )
                    }

                    if ( rel_fields.size() != 3 ) { // Did we start with > 3? That's too weird to continue
                        error( "Unexpected number of fields in release: ${spec.release}" )
                    }

                    if ( BUILD_MODE == "online:int" ) {
                        rel_fields[1] = rel_fields[1].toInteger() + 1  // Bump the INT version
                        rel_fields[2] = 0  // If we are bumping the INT field, everything following is reset to zero
                    }

                    if ( BUILD_MODE == "online:stg" ) {
                        rel_fields[2] = rel_fields[2].toInteger() + 1  // Bump the STG version
                    }

                    NEW_VERSION = spec.version   // Keep the existing spec's version
                    NEW_RELEASE = "${rel_fields[0]}.${rel_fields[1]}.${rel_fields[2]}"

                    // Add a bumpable field for ose_images.sh to increment for image refreshes (i.e. REL.INT.STG.BUMP)
                    NEW_DOCKERFILE_RELEASE = "${NEW_RELEASE}.0"

                } else if ( BUILD_MODE == "release" || BUILD_MODE == "pre-release" ) {

                    /**
                     * Once someone sets the origin.spec Release to 1, we are building release candidates.
                     * If a release candidate is released, its associated images will show up in registry.access
                     * with the tags X.Y.Z-R  and  X.Y.Z. The "R" cannot be used since the fields is bumped by
                     * refresh-images when building images with signed RPMs. That is, if OCP tried to load images
                     * with the X.Y.Z-R' its RPM was built with, the R != R' (since R' < R) and the image
                     * would not be found.
                     * For release candidates, therefore, we must only use X.Y.Z to differentiate builds.
                     *
                     * Note that this problem does not affect online:int & online:stg builds since we control the
                     * tags in the registries. We have refresh-images bump a harmless field in the release and then
                     * craft a tag in the registry [version]-[release] which does not include that bumped field.
                     */
                    if ( rel_fields[0].toInteger() != 1 ) {
                        error( "You need to set the spec Release field to 1 in order to build in this mode" )
                    }

                    // Undertake to increment the last field in the version (e.g. 3.7.0 -> 3.7.1)
                    ver_fields = spec.version.tokenize(".")
                    ver_fields[ver_fields.size()-1] = "${ver_fields[ver_fields.size()-1].toInteger() + 1}"
                    NEW_VERSION = ver_fields.join(".")
                    NEW_RELEASE = "1"
                    NEW_DOCKERFILE_RELEASE = NEW_RELEASE

                } else {
                    error( "Unknown BUILD_MODE: ${BUILD_MODE}" )
                }

                currentBuild.displayName = "#${currentBuild.number} - ${NEW_VERSION}-${NEW_RELEASE} (${BUILD_MODE})"

            }
        }

        stage( "prep web-console" ) {
            dir( WEB_CONSOLE_DIR ) {
                // Unless building for stage, origin-web-console#entperise-X.Y should be used
                if ( BUILD_MODE == "online:stg" ) {
                    WEB_CONSOLE_BRANCH = "stage"
                    sh "git checkout -b stage origin/stage"
                } else {
                    WEB_CONSOLE_BRANCH = "enterprise-${spec.major_minor}"
                    sh "git checkout -b ${WEB_CONSOLE_BRANCH} origin/${WEB_CONSOLE_BRANCH}"
                    if ( IS_SOURCE_IN_MASTER ) {

                        // jwforres asked that master *not* merge into the 3.8 branch.
                        if ( BUILD_VERSION != "3.8" ) {
                            sh """
                                # Pull content of master into enterprise branch
                                git merge master --no-commit --no-ff
                                # Use grunt to rebuild everything in the dist directory
                                ./hack/install-deps.sh
                                grunt build

                                git add dist
                                git commit -m "Merge master into enterprise-${BUILD_VERSION}" --allow-empty
                            """

                            if ( ! IS_TEST_MODE ) {
                                sh "git push"
                            }

                            // Clean up any unstaged changes (e.g. .gitattributes)
                            sh "git reset --hard HEAD"
                        }

                    }
                }
            }
        }

        stage( "merge origin" ) {
            dir( OSE_DIR ) {
                // Enable fake merge driver used in our .gitattributes
                sh "git config merge.ours.driver true"
                // Use fake merge driver on specific packages
                sh "echo 'pkg/assets/bindata.go merge=ours' >> .gitattributes"
                sh "echo 'pkg/assets/java/bindata.go merge=ours' >> .gitattributes"

                if ( UPSTREAM_SOURCE_BRANCH != null ) {
                    // Merge upstream origin code into the ose branch
                    sh "git merge -m 'Merge remote-tracking branch ${UPSTREAM_SOURCE_BRANCH}' ${UPSTREAM_SOURCE_BRANCH}"
                } else {
                    echo "No origin upstream in this build"
                }
            }
        }

        stage( "merge web-console" ) {
            dir( OSE_DIR ) {

                // Vendor a particular branch of the web console into our ose branch and capture the SHA we vendored in
                // TODO: Is this necessary? If we don't specify a GIT_REF, will it just use the current branch
                // we already setup?
                // TODO: Easier way to get the VC_COMMIT by just using parse-rev when we checkout the desired web console branch?
                VC_COMMIT = sh(
                        returnStdout: true,
                        script: "GIT_REF=${WEB_CONSOLE_BRANCH} hack/vendor-console.sh 2>/dev/null | grep 'Vendoring origin-web-console' | awk '{print \$4}'",
                ).trim()

                // Vendoring the console will rebuild this assets, so add them to the ose commit
                sh """
                    git add pkg/assets/bindata.go
                    git add pkg/assets/java/bindata.go
                """
            }
        }

        stage( "ose tag" ) {
            dir( OSE_DIR ) {
                // Set the new version/release value in the file and tell tito to keep the version & release in the spec.
                buildlib.set_rpm_spec_version( "origin.spec", NEW_VERSION )
                buildlib.set_rpm_spec_release_prefix( "origin.spec", NEW_RELEASE )
                // Note that I did not use --use-release because it did not maintain variables like %{?dist}
                sh "tito tag --accept-auto-changelog --keep-version --debug --changelog='Automatic commit of package [atomic-openshift] release [${NEW_VERSION}-${NEW_RELEASE}]; bump origin-web-console ${VC_COMMIT}'"
                if ( ! IS_TEST_MODE ) {
                    sh "git push"
                    sh "git push --tags"
                }
                OSE_CHANGELOG = buildlib.read_changelog( "origin.spec" )
            }
        }

        stage( "openshift-ansible prep" ) {
            OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "master"
            dir( OPENSHIFT_ANSIBLE_DIR ) {
                if ( BUILD_MODE == "online:stg" ) {
                    sh "git checkout -b stage origin/stage"
                    OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "stage"
                } else {
                    if ( ! IS_SOURCE_IN_MASTER ) {
                        // At 3.6, openshift-ansible switched from release-1.X to match 3.X release branches
                        if ( BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6 ) {
                            OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-1.${BUILD_VERSION_MINOR}"
                        } else {
                            OPENSHIFT_ANSIBLE_SOURCE_BRANCH = "release-${BUILD_VERSION}"
                        }
                        sh "git checkout -b ${OPENSHIFT_ANSIBLE_SOURCE_BRANCH} origin/${OPENSHIFT_ANSIBLE_SOURCE_BRANCH}"
                    } else {
                       sh "git checkout master"
                    }
                }
            }
        }

        stage( "openshift-ansible tag" ) {
            dir(OPENSHIFT_ANSIBLE_DIR) {
                if ( BUILD_VERSION_MAJOR == 3 && BUILD_VERSION_MINOR < 6 ) {
                    // Use legacy versioning if < 3.6
                    sh "tito tag --debug --accept-auto-changelog"
                } else {
                    // If >= 3.6, keep openshift-ansible in sync with OCP version
                    buildlib.set_rpm_spec_version( "openshift-ansible.spec", NEW_VERSION )
                    buildlib.set_rpm_spec_release_prefix( "openshift-ansible.spec", NEW_RELEASE )
                    // Note that I did not use --use-release because it did not maintain variables like %{?dist}
                    sh "tito tag --debug --accept-auto-changelog --keep-version --debug"
                }

                if ( ! IS_TEST_MODE ) {
                    sh "git push"
                    sh "git push --tags"
                }
                OA_CHANGELOG = buildlib.read_changelog( "openshift-ansible.spec" )
            }
        }

        if ( IS_TEST_MODE ) {
            error( "This is as far as the test process can proceed without triggering builds" )
        }

        stage( "rpm builds" ) {

            // Allow both brew builds to run at the same time

            dir( OSE_DIR ) {
                OSE_TASK_ID = sh(   returnStdout: true,
                        script: "tito release --debug --yes --test aos-${BUILD_VERSION} | grep 'Created task:' | awk '{print \$3}'"
                )
                OSE_BREW_URL = "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${OSE_TASK_ID}"
                echo "ose rpm brew task: ${OSE_BREW_URL}"
            }
            dir( OPENSHIFT_ANSIBLE_DIR ) {
                OA_TASK_ID = sh(   returnStdout: true,
                        script: "tito release --debug --yes --test aos-${BUILD_VERSION} | grep 'Created task:' | awk '{print \$3}'"
                )
                OA_BREW_URL = "https://brewweb.engineering.redhat.com/brew/taskinfo?taskID=${OA_TASK_ID}"
                echo "openshift-ansible rpm brew task: ${OA_BREW_URL}"
            }

            // Watch the tasks to make sure they succeed. If one fails, make sure the user knows which one by providing the correct brew URL
            try {
                sh "brew watch-task ${OSE_TASK_ID}"
            } catch ( ose_err ) {
                echo "Error in ose build task: ${OSE_BREW_URL}"
                throw ose_err
            }
            try {
                sh "brew watch-task ${OA_TASK_ID}"
            } catch ( oa_err ) {
                echo "Error in openshift-ansible build task: ${OA_BREW_URL}"
                throw oa_err
            }
        }
        
        stage( "build OIT rpms" ) {
          buildlib.oit """
--working-dir ${OIT_WORKING} --group 'openshift-${BUILD_VERSION}'
--sources ${env.WORKSPACE}/sources.yml
rpms:build --version v${NEW_VERSION}
--release ${NEW_DOCKERFILE_RELEASE}
"""
        }

        stage( "signing rpms" ) {
            if ( SIGN_RPMS ) {
                sh "${env.WORKSPACE}/build-scripts/sign_rpms.sh rhaos-${BUILD_VERSION}-rhel-7-candidate openshifthosted"
            } else {
                echo "RPM signing has been skipped..."
            }
        }

        stage( "puddle: ose 'building'" ) {
          buildlib.build_puddle(
                  PUDDLE_CONF,    // The puddle configuration file to use
                  PUDDLE_SIGN_KEYS, // openshifthosted key
                  "-b",   // do not fail if we are missing dependencies
                  "-d",   // print debug information
                  "-n",   // do not send an email for this puddle
                  "-s",   // do not create a "latest" link since this puddle is for building images
                  "--label=building"   // create a symlink named "building" for the puddle
          )
        }

        // TODO: Remove after new OIT version confirmed
        // Old method for most images
        stage( "compare dist-git" ) {
            if ( BUILD_VERSION != "3.8" && BUILD_VERSION != "3.9" ) { // Trying to make all of 3.8/3.9 build with oit
                sh "ose_images.sh --user ocp-build compare_nodocker --branch rhaos-${BUILD_VERSION}-rhel-7 --group base"
            }
        }

        stage( "update dist-git" ) {
            if ( BUILD_VERSION != "3.8" && BUILD_VERSION != "3.9" ) { // Trying to make all of 3.8/3.9 build with oit
                sh "ose_images.sh --user ocp-build update_docker --branch rhaos-${BUILD_VERSION}-rhel-7 --group base --force --release '${NEW_DOCKERFILE_RELEASE}' --version 'v${NEW_VERSION}'"
            }
        }
        // End old method

        stage( "update dist-git" ) {
          buildlib.write_sources_file()
          buildlib.oit """
--working-dir ${OIT_WORKING} --group 'openshift-${BUILD_VERSION}'
--sources ${env.WORKSPACE}/sources.yml
images:rebase --version v${NEW_VERSION}
--release ${NEW_DOCKERFILE_RELEASE}
--message 'Updating Dockerfile version and release v${NEW_VERSION}-${NEW_DOCKERFILE_RELEASE}' --push
"""
        }

        record_log = buildlib.parse_record_log( OIT_WORKING )
        distgit_notify = buildlib.get_distgit_notify( record_log )
        distgit_notify = buildlib.mapToList(distgit_notify)
        // loop through all new commits and notify their owners

        SOURCE_BRANCHES = [
          "ose": OSE_SOURCE_BRANCH,
          "jenkins": JENKINS_SOURCE_BRANCH,
          "openshift-ansible": OPENSHIFT_ANSIBLE_SOURCE_BRANCH
        ]
        for(i = 0; i < distgit_notify.size(); i++) {
            distgit = distgit_notify[i][0]
            val = distgit_notify[i][1]

            try {
              alias = val['source_alias']
              dockerfile_url = ""
              github_url = GITHUB_URLS[alias]
              github_url = github_url.replace(".git", "")
              github_url = github_url.replace("git@", "")
              github_url = github_url.replaceFirst(":", "/")
              dockerfile_sub_path = val['source_dockerfile_subpath']
              dockerfile_url = "Source file: https://" + github_url + "/blob/" + SOURCE_BRANCHES[alias] +"/" + dockerfile_sub_path
              try {
                // always mail success list, val.owners will be comma delimited or empty
                mail(to: "jupierce@redhat.com,smunilla@redhat.com,ahaile@redhat.com,${val.owners}",
                        from: "aos-cd@redhat.com",
                        subject: "${val.image} Dockerfile reconciliation.",
                        body: """
  OIT has detected a change in the Dockerfile for ${val.image}
  ${dockerfile_url}
  This has been automatically reconciled and the new file can be seen here:
  https://pkgs.devel.redhat.com/cgit/${distgit}/tree/Dockerfile?id=${val.sha}
                """);
              } catch ( err ) {

                  echo "Failure sending email"
                  echo "${err}"
              }
            } catch ( err_alias ) {

                echo "Failure resolving alias for email"
                echo "${err_alias}"
            }
        }

        stage( "build images" ) {
            // TODO: Create a dynamic .repo file pointing to the exact puddle we built instead of "building" so that we can run X.Y builds in parallel
            if ( BUILD_VERSION != "3.8" && BUILD_VERSION != "3.9" ) { // Trying to move all 3.8/3.9 images to oit
                sh "ose_images.sh --user ocp-build build_container --branch rhaos-${BUILD_VERSION}-rhel-7 --group base --repo https://raw.githubusercontent.com/openshift/aos-cd-jobs/master/build-scripts/repo-conf/aos-unsigned-building.repo"
            }

            buildlib.oit """
--working-dir ${OIT_WORKING} --group openshift-${BUILD_VERSION}
images:build
--push-to-defaults --repo-type unsigned
"""
        }

        // Old method
        if ( EARLY_LATEST_HACK.toBoolean() ) {
            // Hack to keep from breaking openshift-ansible CI during US Eastern daylight builds. They need the latest puddle to exist
            // before images are pushed to registry-ops in order for their current CI implementation to work.
            OCP_PUDDLE = buildlib.build_puddle(
                    PUDDLE_CONF,    // The puddle configuration file to use
                    PUDDLE_SIGN_KEYS, // openshifthosted key
                    "-b",   // do not fail if we are missing dependencies
                    "-d",   // print debug information
                    "-n"
            )
        }

        stage( "push images" ) {
            dir( "${env.WORKSPACE}/build-scripts/ose_images" ) {
                TAG_LATEST = IS_SOURCE_IN_MASTER?"":"--nolatest"
                if ( BUILD_VERSION != "3.8" && BUILD_VERSION != "3.9" ) { // Trying to get all of 3.8/3.9 building with oit
                    sh "sudo ./ose_images.sh --user ocp-build push_images ${TAG_LATEST} --branch rhaos-${BUILD_VERSION}-rhel-7 --group base"
                }
                try {
                    buildlib.print_tags("openshift3/ose")
                } catch ( cex ) {}
            }
        }

        if ( ! EARLY_LATEST_HACK.toBoolean() ) {
            // If we have not done so already, create the "latest" puddle
            OCP_PUDDLE = buildlib.build_puddle(
                    PUDDLE_CONF,    // The puddle configuration file to use
                    PUDDLE_SIGN_KEYS, // openshifthosted key
                    "-b",   // do not fail if we are missing dependencies
                    "-d",   // print debug information
                    "-n"
            )
        }

        echo "Created puddle on rcm-guest: /mnt/rcm-guest/puddles/RHAOS/AtomicOpenShift/${BUILD_VERSION}/${OCP_PUDDLE}"

        NEW_FULL_VERSION="${NEW_VERSION}-${NEW_RELEASE}"

        // Push the latest puddle out to the correct directory on the mirrors (e.g. online-int, online-stg, or enterprise-X.Y)
        buildlib.invoke_on_rcm_guest( "push-to-mirrors.sh", "simple", NEW_FULL_VERSION, BUILD_MODE )

        // push-to-mirrors.sh sets up a different puddle name on rcm-guest and the mirrors
        OCP_PUDDLE = "${OCP_PUDDLE}_v${NEW_FULL_VERSION}"

        if ( NEW_RELEASE != "1" ) {
            // If this is not a release candidate, push binary in a directory qualified with release field information
            buildlib.invoke_on_rcm_guest( "publish-oc-binary.sh", BUILD_VERSION, NEW_FULL_VERSION )
        } else {
            // If this is a release candidate, the directory binary directory should not contain release information
            buildlib.invoke_on_rcm_guest( "publish-oc-binary.sh", BUILD_VERSION, NEW_VERSION )
        }

        echo "Finished building OCP ${NEW_FULL_VERSION}"
        PREV_BUILD = null  // We are done. Don't untag even if there is an error sending the email.

        mail_success( NEW_FULL_VERSION )
        }
    } catch ( err ) {

        ATTN=""
        try {
                NEW_BUILD = sh(returnStdout: true, script: "brew latest-build --quiet rhaos-${BUILD_VERSION}-rhel-7-candidate atomic-openshift | awk '{print \$1}'").trim()
            if ( PREV_BUILD != null && PREV_BUILD != NEW_BUILD ) {
                // Untag anything tagged by this build if an error occured at any point
                    sh "brew --user=ocp-build untag-build rhaos-${BUILD_VERSION}-rhel-7-candidate ${NEW_BUILD}"
            }
        } catch ( err2 ) {
            ATTN=" - UNABLE TO UNTAG!"
        }

        mail(to: "${MAIL_LIST_FAILURE}",
                from: "aos-cd@redhat.com",
                subject: "Error building OSE: ${BUILD_VERSION}${ATTN}",
                body: """Encountered an error while running OCP pipeline: ${err}

    Jenkins job: ${env.BUILD_URL}
    """);
        throw err
    } finally {
        try {
            archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/*.log"
            archiveArtifacts allowEmptyArchive: true, artifacts: "oit_working/brew-logs/**"
        } catch( aae ) {}
    }


}

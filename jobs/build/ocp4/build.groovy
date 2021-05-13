#!/usr/bin/env groovy

buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

// Properties that should be initialized and not updated
version = [
    stream: "",     // "X.Y" e.g. "4.0"
    branch: "",     // e.g. "rhaos-4.0-rhel-7"
    full: "",       // e.g. "4.0.0"
    release: "",    // e.g. "201901011200"
    major: 0,       // X in X.Y, e.g. 4
    minor: 0,       // Y in X.Y, e.g. 0
]
doozerWorking = "${env.WORKSPACE}/doozer_working" // must be in WORKSPACE to archive artifacts
doozerOpts = "--working-dir ${doozerWorking}"

// this plan is to be initialized but then adjusted for incremental builds
buildPlan = [
    dryRun: false, // report build plan without performing it
    forceBuild: false, // build regardless of whether source has changed
    buildRpms: false,
    rpmsIncluded: "", // comma-separated list
    rpmsExcluded: "", // comma-separated list
    buildImages: false,
    imagesIncluded: "", // comma-separated list
    imagesExcluded: "", // comma-separated list
]
// These values are filled in later by stageBuildCompose
rpmMirror = [       // how to mirror RPM compose
    composeName: "", // The name of the yum repo directory created.
    localComposePath: "",  // will be populated with full path to yum repo created on buildvm
    url: "", // url to directory where new repo can be found after mirroring
]

/**
 * Initialize properties from Jenkins parameters.
 * @return map which is the buildPlan property of this build.
*/
def initialize() {
    buildlib.cleanWorkdir(doozerWorking)
    buildlib.initialize()
    GITHUB_BASE = "git@github.com:openshift"  // buildlib uses this :eyeroll:

    currentBuild.displayName = "#${currentBuild.number} - ${params.BUILD_VERSION}.??"
    echo "Initializing build: ${currentBuild.displayName}"

    version.stream = params.BUILD_VERSION.trim()
    doozerOpts += " --group 'openshift-${version.stream}'"
    version.branch = buildlib.getGroupBranch(doozerOpts)
    version << determineBuildVersion(version.stream, version.branch)

    buildPlan << [
        dryRun: params.DRY_RUN,
        forceBuild: params.FORCE_BUILD,
        buildRpms: params.BUILD_RPMS != "none",
        buildImages: params.BUILD_IMAGES != "none",
    ]

    // determine whether the user wanted to specify includes or excludes
    rpmList = [only: "rpmsIncluded", except: "rpmsExcluded"][params.BUILD_RPMS]
    if (rpmList) {
        buildPlan[rpmList] = commonlib.cleanCommaList(params.RPM_LIST)
    } else if (params.RPM_LIST.trim()) {
        error("aborting because a list of RPMs was specified; you probably want to specify only/except.")
    }

    imageList = [only: "imagesIncluded", except: "imagesExcluded"][params.BUILD_IMAGES]
    if (imageList) {
        buildPlan[imageList] = commonlib.cleanCommaList(params.IMAGE_LIST)
    } else if (params.IMAGE_LIST.trim()) {
        error("aborting because a list of images was specified; you probably want to specify only/except.")
    }

    echo "Initial build plan: ${buildPlan}"

    // and where to mirror the compose when it's done
    rpmMirror.url = "https://mirror.openshift.com/enterprise/enterprise-${version.stream}"

    // adjust the build "title"
    currentBuild.displayName = "#${currentBuild.number} - ${version.full}-${version.release}"
    if (buildPlan.dryRun) { currentBuild.displayName += " [DRY RUN]" }
    if (buildPlan.forceBuild) { currentBuild.displayName += " [force build]" }
    if (!buildPlan.buildRpms) { currentBuild.displayName += " [no RPMs]" }
    if (!buildPlan.buildImages) { currentBuild.displayName += " [no images]" }

    return planBuilds()
}

/**
 * From the minor version (stream) and parameters, determine which version to build.
 * @param stream: OCP minor version "X.Y"
 * @return a map to merge into the "version" property representing the determined version
 */
def determineBuildVersion(stream, branch) {
    def segments = stream.tokenize('.').collect { it.toInteger() }
    return [
        major: segments[0],
        minor: segments[1],
        full: buildlib.determineBuildVersion(stream, branch, params.NEW_VERSION.trim()),
        release: buildlib.defaultReleaseFor(stream),
    ]
}

def displayTagFor(commaList, kind, isExcluded=false){
    def items = commaList.split(',')
    def desc = items.size() == 1 ? items[0] : "${items.size()}"
    def plurality = items.size() == 1 ? kind : "${kind}s"
    return isExcluded ? " [${kind}s except ${desc}]" : " [${desc} ${plurality}]"
}


/**
 * Plan what will be built.
 * Figure out whether we're building RPMs and/or images, and which ones, based on
 * the parameters and which sources have changed (if relevant).
 * Fills in the "buildPlan" property for later stages to use.
 * @return map which is the buildPlan property of this build.
 */
def planBuilds() {
    if (buildPlan.forceBuild) {
        currentBuild.description = "Force building (whether source changed or not).<br/>"
        currentBuild.description +=
            (!buildPlan.buildRpms) ? "RPMs: not building.<br/>" :
            (buildPlan.rpmsIncluded) ? "RPMs: building ${buildPlan.rpmsIncluded}.<br/>" :
            (buildPlan.rpmsExcluded) ? "RPMs: building all except ${buildPlan.rpmsExcluded}.<br/>" :
            "RPMs: building all.<br/>"
        currentBuild.displayName +=
            (buildPlan.rpmsIncluded) ? displayTagFor(buildPlan.rpmsIncluded, "RPM") :
            (buildPlan.rpmsExcluded) ? displayTagFor(buildPlan.rpmsExcluded, "RPM", true) :
            (buildPlan.buildRpms) ? " [all RPMs]" : ""

        currentBuild.description += "Will create RPM compose.<br/>"
        currentBuild.description +=
            (!buildPlan.buildImages) ? "Images: not building.<br/>" :
            (buildPlan.imagesIncluded) ? "Images: building ${buildPlan.imagesIncluded}.<br/>" :
            (buildPlan.imagesExcluded) ? "Images: building all except ${buildPlan.imagesExcluded}.<br/>" :
            "Images: building all.<br/>"
        currentBuild.displayName +=
            (buildPlan.imagesIncluded) ? displayTagFor(buildPlan.imagesIncluded, "image") :
            (buildPlan.imagesExcluded) ? displayTagFor(buildPlan.imagesExcluded, "image", true) :
            (buildPlan.buildImages) ? " [all images]" : ""
        return buildPlan
    }

    // otherwise we need to scan sources.
    echo "Building only where source has changed."
    currentBuild.description = "Building sources that have changed.<br/>"

    def changed = [:]
    try {
        def yamlStr = buildlib.doozer(
            """
            ${doozerOpts}
            ${includeExclude "rpms", buildPlan.rpmsIncluded, buildPlan.rpmsExcluded}
            ${includeExclude "images", buildPlan.imagesIncluded, buildPlan.imagesExcluded}
            config:scan-sources --yaml
            """, [capture: true]
        )
		echo "scan-sources output:\n${yamlStr}\n\n"

		def yamlData = readYaml text: yamlStr

        changed = buildlib.getChanges(yamlData)

        def report = { msg ->
            echo msg
            currentBuild.description += "${msg}<br/>"
        }
        if (!buildPlan.buildRpms) {
            report "RPMs: not building."
            report "Will not create RPM compose if automation is frozen."
        } else if (changed.rpms) {
            report "RPMs: building " + changed.rpms.join(", ")
            report "Will create RPM compose."
            buildPlan.rpmsIncluded = changed.rpms.join(",")
            buildPlan.rpmsExcluded = ""
            currentBuild.displayName += displayTagFor(buildPlan.rpmsIncluded, "RPM")
        } else {
            buildPlan.buildRpms = false
            report "RPMs: none changed."
            report "Will still create RPM compose."
            currentBuild.displayName += " [no changed RPMs]"
        }

        if (!buildPlan.buildImages) {
            report "Images: not building."
            return buildPlan
        } else if (!changed.images) {
            report "Images: none changed."
            buildPlan.buildImages = false
            currentBuild.displayName += " [no changed images]"
            return buildPlan
        }
        report "Found ${changed.images.size()} image(s) with changes:\n  " + changed.images.join("\n  ")

        // also determine child images of changed
        yamlData = readYaml text: buildlib.doozer(
            """
            ${doozerOpts}
            ${includeExclude "images", buildPlan.imagesIncluded, buildPlan.imagesExcluded}
            images:show-tree --yml
            """, [capture: true]
        )

        // scan the image tree for changed and their children using recursive closure
        Closure gather_children  // needs to be defined separately to self-call
        gather_children = { all, data, initial, gather ->
            // all(list): all images gathered so far while traversing tree
            // data(map): the part of the yaml image tree we're looking at
            // initial(list): all images initially found to have changed
            // gather(bool): whether this is a subtree of an image with changed source
            data.each { image, children ->
                def gather_this = gather || image in initial
                if (gather_this) {  // this or an ancestor was a changed image
                    all.add(image)
                }
                // scan children recursively
                all = gather_children(all, children, initial, gather_this)
            }
            return all
        }
        def images = gather_children([], yamlData, changed.images, false)
        children = images - changed.images
        if (children) {
            report "Images: also building ${children.size()} child(ren):\n  " + children.join("\n  ")
        }
        buildPlan.imagesIncluded = images.join(",")
        buildPlan.imagesExcluded = ""
        currentBuild.displayName += displayTagFor(buildPlan.imagesIncluded, "image")

        // NOTE: it might be nice not to rebase child images where the source hasn't changed.
        // However we would still need to update dockerfile for those images; but running doozer
        // separately for rebase and update-dockerfile would mess up parent-child relationships,
        // and it isn't worth the trouble to make that work.
    } catch (err) {
        currentBuild.description += "error during plan builds step:<br/>${err.getMessage()}<br/>"
        throw err
    }
    return buildPlan
}

// determine what doozer parameter (if any) to use for includes/excludes
def includeExclude(kind, includes, excludes) {
    // --latest-parent-version only applies for images but won't hurt for RPMs
    if (includes) { return "--latest-parent-version --${kind} ${includes}" }
    if (excludes) { return "--latest-parent-version --${kind} '' --exclude ${excludes}" }
    return "--${kind} ''"
}

def stageBuildRpms() {
    if (!buildPlan.buildRpms) {
        echo "Not building RPMs."
        return
    }
    def cmd =
        """
        ${doozerOpts}
        ${includeExclude "rpms", buildPlan.rpmsIncluded, buildPlan.rpmsExcluded}
        rpms:rebase-and-build --version v${version.full}
        --release '${version.release}'
        """

    buildPlan.dryRun ? echo("doozer ${cmd}") : buildlib.doozer(cmd)
}

/**
 * Unless no RPMs have changed, create multiple yum repos (one for each arch) of RPMs based on -candidate tags.
 * Based on commonlib.ocpReleaseState, those repos can be signed (release state) or unsigned (pre-release state).
 */
def stageBuildCompose() {
    if(buildPlan.dryRun) {
        echo "Running in dry-run mode -- will not run plashet."
        return
    }

    def auto_signing_advisory = Integer.parseInt(buildlib.doozer("${doozerOpts} config:read-group --default=0 signing_advisory", [capture: true]).trim())

    buildlib.buildBuildingPlashet(version.full, version.release, 8, true, auto_signing_advisory)  // build el8 embargoed plashet
    buildlib.buildBuildingPlashet(version.full, version.release, 7, true, auto_signing_advisory)  // build el7 embargoed plashet
    buildlib.buildBuildingPlashet(version.full, version.release, 8, false, auto_signing_advisory)  // build el8 unembargoed plashet
    def plashet = buildlib.buildBuildingPlashet(version.full, version.release, 7, false, auto_signing_advisory)  // build el7 unembargoed plashet
    rpmMirror.plashetDirName = plashet.plashetDirName
    rpmMirror.localPlashetPath = plashet.localPlashetPath
}

def stageUpdateDistgit() {
    if (!buildPlan.buildImages) {
        echo "Not rebasing images."
        return
    }
    def cmd =
        """
        ${doozerOpts}
        ${includeExclude "images", buildPlan.imagesIncluded, buildPlan.imagesExcluded}
        images:rebase --version v${version.full} --release '${version.release}'
        --message 'Updating Dockerfile version and release v${version.full}-${version.release}' --push
        --message '${env.BUILD_URL}'
        """
    if(buildPlan.dryRun) {
        echo "${buildlib.DOOZER_BIN} ${cmd}"
        return
    }
    buildlib.doozer(cmd)
    // TODO: if rebase fails for required images, notify image owners, and still notify on other reconciliations
    buildlib.notify_dockerfile_reconciliations(doozerWorking, version.stream)
    // TODO: if a non-required rebase fails, notify ART and the image owners

    buildlib.notify_bz_info_missing(doozerWorking, version.stream)
}

/**
 * Build the images according to plan.
 */
def stageBuildImages() {
    if (!buildPlan.buildImages) {
        echo "Not building images."
        return
    }
    try {

        def archReleaseStates = commonlib.ocpReleaseState[version.stream]
        // If any arch is GA, use signed for everything. See stageBuildCompose for details.
        def signing_mode = archReleaseStates['release']?'signed':'unsigned'
        def cmd =
            """
            ${doozerOpts}
            ${includeExclude "images", buildPlan.imagesIncluded, buildPlan.imagesExcluded}
            images:build
            --repo-type ${signing_mode}
            """
        if(buildPlan.dryRun) {
            echo "${buildlib.DOOZER_BIN} ${cmd}"
            return
        }
        buildlib.doozer(cmd)
    }
    catch (err) {
        recordLog = buildlib.parse_record_log(doozerWorking)
        def failed_map = buildlib.get_failed_builds(recordLog, true)
        if (!failed_map) { throw err }  // failed so badly we don't know what failed; give up

        failed_images = failed_map.keySet()
        currentBuild.result = "UNSTABLE"
        currentBuild.description += "Failed images: ${failed_images.join(', ')}<br/>"

        def r = buildlib.determine_build_failure_ratio(recordLog)
        if (r.total > 10 && r.ratio > 0.25 || r.total > 1 && r.failed == r.total) {
            echo "${r.failed} of ${r.total} image builds failed; probably not the owners' fault, will not spam"
        } else {
            buildlib.mail_build_failure_owners(failed_map, "aos-team-art@redhat.com", params.MAIL_LIST_FAILURE)
        }
    }

	recordLog = buildlib.parse_record_log(doozerWorking)
	def success_map = buildlib.get_successful_builds(recordLog, true)
	if (success_map.containsKey('ose-openshift-apiserver')) {
        // If the API server builds, we mirror out the streams to CI. If ART builds a bad golang builder image
        // it will break CI builds for most upstream components if we don't catch it before we push. So we use
        // apiserver as bellweather to make sure that the currently builder image is good enough. We can still
        // break CI (e.g. pushing a bad ruby-25 image along with this push, but it will not be a catastrophic
        // event like breaking the apiserver.

        // Make sure our api.ci token is fresh
        sh "oc --kubeconfig=${buildlib.ciKubeconfig} registry login"

        buildlib.doozer "${doozerOpts} images:streams mirror"
    }
}

/**
 * Copy the plashet created earlier out to the openshift mirrors. This allows QE to
 * easily find the RPMs we used in the creation of the images. These RPMs may be
 * required for bare metal installs.
 */
def stageMirrorRpms() {
    if (!rpmMirror.localPlashetPath) {
        echo "No updated RPMs to mirror."
        return
    }

    def openshift_mirror_bastion = "use-mirror-upload.ops.rhcloud.com"
    def openshift_mirror_user = "jenkins_aos_cd_bot"
    def destBaseDir = "/srv/enterprise/enterprise-${version.stream}"
    def stagingDir = "${destBaseDir}/staging"

    if (buildPlan.dryRun) {
        echo "Would have copied plashet to ${openshift_mirror_user}@${openshift_mirror_bastion}:${destBaseDir}"
        return
    }

    /**
     * Just in case this is the first time we have built this release, create the release's staging directory.
     * What is staging? Glad you asked. rsync isn't dumb. If it finds a remote file already present,
     * it will avoid transferring the source file. That means you can dramatically speed up rsync if your
     * source and destination on differ by a little.
     * Each time we build 4.x, probably only a few RPMs actually change. So, we have a 4.x staging directory
     * we rsync to.
     */
    commonlib.shell("ssh ${openshift_mirror_user}@${openshift_mirror_bastion} -- mkdir -p ${stagingDir}")
    commonlib.shell([
            "rsync",
            "-av",  // archive mode, verbose
            "--copy-links",  // The local repo is composed of symlinks to brewroot; use-mirror does not have brewroot mounted, so we need to copy content, not the symlinks
            "--progress",
            "-h", // human readable numbers
            "--no-g",  // use default group on mirror for the user we are logging in with
            "--omit-dir-times",
            "--delete-after", // anything that was in staging, but is no longer there, delete it after a successful transfer
            "--chmod=Dug=rwX,ugo+r",
            "--perms",
            "${rpmMirror.localPlashetPath}/",  // local directory we just built with plashet. NOTICE THE TRAILILNG slash. This means copy the files within, but not the directory name.
            "${openshift_mirror_user}@${openshift_mirror_bastion}:${stagingDir}"  // we want the arch repos to land in staging.
    ].join(" "))

    // We now have a staging plashet out on the mirror bastion with yum repo content. Now we need to
    // make copy of it with the real plashet name. We could use hardlinks, but that seems to cause issues
    // with the mirror infrastructure's replication to subordinates.
    commonlib.shell("ssh ${openshift_mirror_user}@${openshift_mirror_bastion} -- cp -a ${stagingDir} ${destBaseDir}/${rpmMirror.plashetDirName}")
    //  Now we have a plashet named after the original on the mirror. QE wants a 'latest' link there.
    commonlib.shell("ssh -t ${openshift_mirror_user}@${openshift_mirror_bastion} \"cd ${destBaseDir}; ln -sfn ${rpmMirror.plashetDirName} latest\"")
    //  Because the mirrors are always low on space, delete all but the lastest 4 plashets
    commonlib.shell("""ssh -t ${openshift_mirror_user}@${openshift_mirror_bastion} 'cd ${destBaseDir};  rm -rf `ls | grep "4.*" | sort | tac | tail -n +5`  '""")
    //  For historical reasons, all puddles were linked to from 'all' directory as well.
    commonlib.shell("""ssh ${openshift_mirror_user}@${openshift_mirror_bastion} -- ln -sfn ${destBaseDir}/${rpmMirror.plashetDirName} /srv/enterprise/all/${version.stream}/${rpmMirror.plashetDirName}""")
    // Also establish latest link
    commonlib.shell("ssh -t ${openshift_mirror_user}@${openshift_mirror_bastion} \"cd /srv/enterprise/all/${version.stream}; ln -sfn ${rpmMirror.plashetDirName} latest\"")
    // Instruct the mirror infrastructure to push content to the subordinate hosts.
    commonlib.shell("ssh ${openshift_mirror_user}@${openshift_mirror_bastion} -- push.enterprise.sh -v  enterprise-${version.stream}")
    commonlib.shell("ssh ${openshift_mirror_user}@${openshift_mirror_bastion} -- push.enterprise.sh -v  all")

    echo "Finished mirroring OCP ${version.full} to openshift mirrors"
}

def stageSyncImages() {
    if (!buildPlan.buildImages) {
        echo "No built images to sync."
        return
    }
    if(buildPlan.dryRun) {
        echo "Not syncing images in a dry run."
        return
    }
    buildlib.sync_images(
        version.major,
        version.minor,
        "aos-team-art@redhat.com",
        currentBuild.number
    )
}

def stagePushQEImages() {
    def cmd =
            """
            ${doozerOpts}
            ${includeExclude "images", buildPlan.imagesIncluded, buildPlan.imagesExcluded}
            images:push
            --to-defaults
            --filter-by-os='.*'
            """
    if(buildPlan.dryRun) {
        echo "doozer ${cmd}"
        return
    }
    try {
        buildlib.doozer(cmd)
    } catch (err) {
        currentBuild.description += "\n<br>image push to qe quay did not completely succeed"
        currentBuild.result = "UNSTABLE"
    }
}

def stageReportSuccess() {
    def builtNothing = buildPlan.dryRun || !(buildPlan.buildRpms || buildPlan.buildImages)
    def recordLog = builtNothing ? [:] : buildlib.parse_record_log(doozerWorking)
    def timingReport = getBuildTimingReport(recordLog)
    currentBuild.description += "<hr />Build results:<br/><br/>${timingReport}"

	def stateYaml = [:]
	if (fileExists("doozer_working/state.yaml")) {
		stateYaml = readYaml(file: "doozer_working/state.yaml")
	}
    messageSuccess(rpmMirror.url)
}

def messageSuccess(mirrorURL) {
    if (!buildPlan.buildImages) {
        echo "No images built so no need for UMB message."
        return
    }
    try {
        timeout(3) {
            sendCIMessage(
                messageContent: "New build for OpenShift: ${version.full}",
                messageProperties:
                    """build_mode=pre-release
                    puddle_url=${rpmMirror.url}/${rpmMirror.plashetDirName}
                    image_registry_root=registry.reg-aws.openshift.com:443
                    product=OpenShift Container Platform
                    """,
                messageType: 'ProductBuildDone',
                overrides: [topic: 'VirtualTopic.qe.ci.jenkins'],
                providerName: 'Red Hat UMB'
            )
        }
    } catch (mex) {
        echo "Error while sending CI message: ${mex.getMessage()}"
    }
}

// extract timing information from the recordLog and write a report string
// the timing record log entry has this form:
// image_build_metrics|elapsed_total_minutes={d}|task_count={d}|elapsed_wait_minutes={d}|
def getBuildTimingReport(recordLog) {
    metrics = recordLog['image_build_metrics']

    if (metrics == null || metrics.size() == 0) {
        return "No images actually built."
    }

    return """
Images built: ${metrics[0]['task_count']}
Elapsed image build time: ${metrics[0]['elapsed_total_minutes']} minutes
Time spent waiting for OSBS capacity: ${metrics[0]['elapsed_wait_minutes']} minutes
"""
}

// get the list of images built
def getImageBuildReport(recordLog) {
    builds = recordLog['build']

    if ( builds == null ) {
        return ""
    }

    Set imageSet = []
    for (i = 0; i < builds.size(); i++) {
        bld = builds[i]
        if (bld['status'] == "0" && bld['push_status'] == "0") {
            imageSet << "${bld['image']}:${bld['version']}-${bld['release']}"
        }
    }

    return "\nImages included in build:\n    " +
        imageSet.toSorted().join("\n    ")
}

return this

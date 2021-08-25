buildlib = load('pipeline-scripts/buildlib.groovy')
commonlib = buildlib.commonlib
slacklib = commonlib.slacklib

doozer_working = "${WORKSPACE}/doozer_working"
elliott_working = "${WORKSPACE}/elliott_working"
buildlib.cleanWorkdir(doozer_working)
buildlib.cleanWorkdir(elliott_working)
doozer_opts = "--working-dir ${doozer_working} -g openshift-${params.BUILD_VERSION}"
elliott_opts = "--working-dir ${elliott_working} -g openshift-${params.BUILD_VERSION}"

/*
 * Return the brew package name of all OLM operators present in <params.BUILD_VERSION>
 */
def get_olm_operators() {
    buildlib.doozer("${doozer_opts} olm-bundle:list-olm-operators", [capture: true]).split("\n").findAll { !it.isEmpty() }
}

/*
 * Make sure 2 advisories belong to the same group that is given
 */
def validate_advisories(advisory1, advisory2, group) {
    def adv1_str = buildlib.elliott("${elliott_opts} get ${advisory1}", [capture: true])
    def adv2_str = buildlib.elliott("${elliott_opts} get ${advisory2}", [capture: true])
    echo adv1_str
    echo adv2_str

    // validate advisory1 string contains group(4.7)
    adv1 = adv1_str.split()
    index = adv1.findIndexOf { it.contains(group) }
    if (index == -1) {
        error("Group ${group} not found in advisory ${advisory1} data. Exiting")
    }

    // validate the version of advisory1(4.7.4) is in advisory2 string
    version = adv1[index]
    if (!adv2_str.contains(version)) {
        error("Version mismatch. ${version} not found in advisory ${advisory2} data. Exiting")
    }
}

/*
 * Return list of OLM Operator NVRs attached to given <advisory>
 */
def get_builds_from_advisory(advisory) {
    def json = buildlib.elliott("${elliott_opts} get --json - ${advisory}", [capture: true])
    readJSON(text: json).errata_builds.values().flatten()
}

/*
 * Build corresponding bundle containers for given operators
 * :param only: list of operator distgit names to include in the build
 * :param exclude: list of operator distgit names to exclude from the build
 * :param operator_nvrs: only build bundles for given <operator_nvrs>
 * Return a list of built <bundle_nvrs>
 */
def build_bundles(String[] only, String[] exclude, String[] operator_nvrs) {
    def cmd = ""
    if (only)
        cmd += " --images=${only.join(',')}"
    if (exclude)
        cmd += " --exclude=${exclude.join(',')}"
    cmd += " olm-bundle:rebase-and-build"
    if (params.FORCE_BUILD)
        cmd += " --force"
    if (params.DRY_RUN)
        cmd += " --dry-run"
    cmd += " -- "
    cmd += operator_nvrs.join(' ')
    buildlib.doozer("${doozer_opts} ${cmd}")
    def record_log = buildlib.parse_record_log(doozer_working)
    def records = record_log.get('build_olm_bundle', [])
    def bundle_nvrs = []
    for (record in records) {
        if (record['status'] != '0') {
            throw new Exception("record.log includes unexpected build_olm_bundle record with error message: ${record['message']}")
        }
        bundle_nvrs << record["bundle_nvr"]
    }
    return bundle_nvrs
}

/*
 * Attach given <bundle_nvrs> to <advisory>
 */
def attach_bundles_to_advisory(bundle_nvrs, advisory) {
    buildlib.elliott("${elliott_opts} change-state -s NEW_FILES -a ${advisory} ${params.DRY_RUN ? '--noop' : ''}")
    flags = bundle_nvrs.collect { "--build ${it}" }.join(' ')
    buildlib.elliott("""${elliott_opts} find-builds -k image ${flags} ${params.DRY_RUN ? '' : "--attach ${advisory}"}""")
    sleep(30) // wait for ET validations to be complete
    buildlib.elliott("${elliott_opts} change-state -s QE -a ${advisory} ${params.DRY_RUN ? '--noop' : ''}")
}

/*
 * Archive artifacts of possible interest from the doozer working directory.
 */
def archiveDoozerArtifacts() {
    commonlib.safeArchiveArtifacts([
        "doozer_working/*.log",
        "doozer_working/*.yaml",
        "doozer_working/brew-logs/**",
    ])
}

return this

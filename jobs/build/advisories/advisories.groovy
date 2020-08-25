buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib

ADVISORIES = [:]

def create_advisory(name) {
    impetus = "${params.IMPETUS}"
    if (name ==~ /.*rhsa$/) {
        impetus = "cve"
    } else if (name == "metadata") {
        impetus = "metadata"
    } else if (name == "extras") {
        impetus = "extras"
    }

    kind = "image"
    if (name ==~ /rpm/) {
        kind = "rpm"
    }

    type = "RHBA"
    if (name ==~ /rhsa/) {
        type = "RHSA"
    } else if (impetus == "ga") {
        type = "RHEA"
    }

    create_cmd = [
        "--group openshift-${params.VERSION}",
        "create",
        "--kind ${kind}",
        "--type ${type}",
        "--impetus ${impetus}",
        "--assigned-to ${params.ASSIGNED_TO}",
        "--manager ${params.MANAGER}",
        "--package-owner ${params.PACKAGE_OWNER}"
    ].join(" ")

    if (params.DATE != null) {
        create_cmd += " --date ${params.DATE}"
    }
    if (params.DRY_RUN != true) {
        create_cmd += " --yes"
    }

    out = buildlib.elliott(create_cmd, [capture: true])
    echo "out: ${out}"

    advisory_id = buildlib.extractAdvisoryId(out)
    ADVISORIES << ["${name}": "${advisory_id}"]
    currentBuild.description += "${name}:  https://errata.devel.redhat.com/advisory/${advisory_id}<br />"
}

def create_placeholder(kind) {
    cmd = [
        "--group openshift-${params.VERSION}",
        "create-placeholder",
        "--kind ${kind}",
        "--use-default-advisory ${kind}"
    ].join(' ')
    echo "elliott cmd: ${cmd}"
    if (params.DRY_RUN) {
        out = "DRY RUN mode, command did not run"
    } else {
        out = buildlib.elliott(cmd, [capture: true])
    }
    echo "out: ${out}"
}

return this

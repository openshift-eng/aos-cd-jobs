#!/usr/bin/env python

"""
PURPOSE
 * This script only tags builds into pending
 * Builds get into builroot via buildroot-push tag (rcm-common/bin/push_to_buildroot)
 * Builds get into released/main tag via move-pushed-erratum in errata tool in post push tasks
 * Original/legacy script is still available as sync_brew_with_errata (lot of redundancy and slow)
"""
from __future__ import print_function
import optparse
import urllib3
import koji
import xmlrpclib
import logging
import sys
import time
from kobo.rpmlib import compare_nvr

def get_logger_name():
    try:
        return __file__
    except NameError:
        return sys.argv[0]

#: This is our log object, clients of this library can use this
#: object to define their own logging needs

BREW_URL = "https://brewhub.engineering.redhat.com/brewhub"
ERRATA_URL = "http://errata-xmlrpc.devel.redhat.com/errata/errata_service"
ERRATA_API_URL = "https://errata.engineering.redhat.com/api/v1/"

DROPPED_STATES = ["DROPPED"]
SHIPPED_STATES = ["SHIPPED_LIVE"]

BREW_EMBARGOED_TAG = "embargoed"

def tag_builds(koji_proxy, tag, nvrs, tagged_builds, test=False):
    """
    tag_builds from nvrs into tag, skip already tagged ones
    Args:
        koji_proxy
        tag: buildroot push tag
        nvrs: list of nvrs
        tagged_builds: dict {nvr: build_info_hash}
        test=False
    """
    tasks = []  # lists of tasks associated with the tagging requests
    failed = False
    for nvr in sorted(nvrs):
        if not nvr in tagged_builds:
            logging.debug("tag_builds: %s is not tagged.", nvr)
            if not test:
                logging.info("tag_builds: Tagging build: %s", nvr)
                try:
                    task = koji_proxy.tagBuild(tag, nvr) # non-blocking
                    # Returned task is a type int
                    tasks.append(task)
                except Exception as e:
                    logging.warn("%s not allowed: %s", nvr, e)
                    failed = e
            else:
                logging.info("tag_builds: Would tag %s into %s", nvr, tag)
        else:
            logging.debug("tag_builds: Build %s is already tagged.", nvr)

    task_failures = False
    for task_id in tasks:
        print('Waiting for task {} to finish'.format(task_id))
        while not koji_proxy.taskFinished(task_id):
            print('.', end='')
            time.sleep(30)
        print()
        tag_res = koji_proxy.getTaskResult(task_id, raise_fault=False)
        if tag_res and 'faultCode' in tag_res:
            print('Failed tagging task! {}\n{}'.format(task_id, tag_res))
            task_failures = True

    if task_failures:
        raise IOError('At least one tagging task failed')

    if failed:
        raise failed

def untag_builds(koji_proxy, tag, nvrs, tagged_builds, test=False):
    """
    untag builds from tagged_builds if the buildroot push flag is removed
    otherwise just keep on tagging on top of each other
    Args:
        koji_proxy
        tag: buildroot push tag
        nvrs: list of nvrs
        tagged_builds: dict {nvr: build_info_hash}
        test=False
    """
    # let's iterate over builds which are actually tagged (less)
    #
    # untag only builds which are in errata and buildroot-push is not set.
    # Which implies that somebody cancelled the flag. 
    for nvr in sorted(tagged_builds):
        if nvr in nvrs:
            logging.debug("untag_builds: %s is tagged", nvr)
            if not test:
                logging.info("untag_builds: Untagging build: %s", nvr)
                koji_proxy.untagBuild(tag, nvr) # non-blocking
            else:
                logging.info("untag_builds: Would untag %s from %s", nvr, tag)

def _diff_me(a_builds, b_builds):
    """
    Returns set of nvrs which are in a but not in b
    Args:
        a_builds list or set of nvrs
        b_builds list or set of nvrs
    """
    logging.debug("a_builds: %s" % a_builds)
    logging.debug("b_builds: %s" % b_builds)

    return set(b_builds).difference(set(a_builds))

def get_missing_builds(errata, tagged):
    """
    Returns dict nvr: build_info  for builds which are in errata but not in pending
    """
    return _diff_me(tagged, errata)

def get_extra_builds(errata, tagged):
    """
    Returns dict nvr: build_info  for builds which are in pending but not in errata
    """
    return _diff_me(errata, tagged)

def get_errata_builds(errata_proxy, errata_group,
                      errata_product, module_builds=False, errata_product_version=None):
    """
    returs dict {nvr: build_info} doesn't actually fetch build info from koji
        to get result faster
    Args:
        errata_proxy
        errata_group
        errata_product
        errata_product_version
    """

    errata_builds = {}


    for advisory in errata_proxy.get_advisory_list(dict(group=errata_group,
        product=errata_product)):
        logging.debug("Checking advisory %s", advisory["errata_id"])

        if advisory["status"] in DROPPED_STATES:
            logging.debug("Skipping because it is DROPPED")
            continue

        if advisory["status"] in SHIPPED_STATES:
            logging.debug("Skipping advisory as it is SHIPPED and it's already in released tag.")
            continue

        if advisory["status"] == "NEW FILES":
            logging.debug("Skipping advisory as it is in New Files thus it doesn't contain signed builds")
            continue

        logging.debug("Getting builds from advisory: %s", advisory["errata_id"])
        for build in errata_proxy.getErrataBrewBuilds(advisory["errata_id"]):
            nvr = build["brew_build_nvr"]
            logging.debug("Checking NVR %s", nvr)
            if errata_product_version:
                product_version = build["product_version"]["name"]
                if product_version != errata_product_version:
                    logging.debug("skipping build it's not in specified product version: %s",
                        nvr, product_version, ', '.join(errata_product_version))
                    continue
            is_module = build["is_module"]
            if module_builds and not is_module:
                   continue
            if not module_builds and is_module:
                   continue
            build_info = {}
            build_info["build_flags"] = build["build_flags"]
            errata_builds[nvr] = build_info
            logging.debug("NVR %s added", nvr)

    return errata_builds


def get_brew_builds(koji_proxy, brew_tags, latest=False, inherit=False):
    """
    """
    brew_builds_by_name = {}
    brew_builds = set()

    if not brew_tags:
        brew_tags = []
    if isinstance(brew_tags, basestring):
        brew_tags = [brew_tags]

    for brew_tag in brew_tags:
        for build in koji_proxy.listTagged(brew_tag, latest=latest, inherit=inherit):
            if latest:
                previous_build = brew_builds_by_name.get(build["name"])
                if not previous_build or compare_nvr(previous_build, build) == 1:
                    brew_builds_by_name[build["name"]] = build
                    brew_builds.remove(previous_build)
                    brew_builds.add(build["nvr"])
            else:
                brew_builds.add(build["nvr"])
    return brew_builds

def main():
    parser = optparse.OptionParser("%prog --errata-group=NAME" \
            "--errata-product=NAME --brew-pending-tag=NAME")
    parser.add_option(
        "--brew-pending-tag",
        metavar="NAME",
        help="Required. Main Brew tag. Example: rhel-7.0",
    )

    parser.add_option(
        "--errata-product",
        metavar="NAME",
        help="Required. Name of Product in Errata Tool.",
    )
    parser.add_option(
        "--errata-product-version",
        dest="errata_product_version",
        metavar="VERSION",
        help="Example: RHEL-7.5",
    )
    parser.add_option(
        "--errata-group",
        metavar="NAME",
        action="append",
        default=[],
        help="Required. Errata release. May be specified multiple times. Example: RHEL-7.0.0",
    )
    parser.add_option(
        "--brew-url",
        default=BREW_URL,
        help="Brew hub URL, default: %s" % BREW_URL
    )
    parser.add_option(
        "--errata-xmlrpc-url",
        default=ERRATA_URL,
        help="Errata Tool XMLRPC URL, default: %s" % ERRATA_URL
    )
    parser.add_option(
        "--errata-api-url",
        default=ERRATA_API_URL,
        help="Errata Tool REST API URL, default: %s" % ERRATA_API_URL
    )
    parser.add_option(
        "--test",
        action="store_true",
        help="Do not execute any tagging operation."
    )
    parser.add_option(
        "--brew-source-tag",
        action="append",
        help=optparse.SUPPRESS_HELP
    )
    parser.add_option(
        "--brew-ignore-embargoed-tag",
        action="store_true",
        help=("Allow builds into destination tag even if tagged into the Brew 'embargoed' tag.")
    )
    parser.add_option(
        "--brew-embargoed-tag-name",
        default=BREW_EMBARGOED_TAG,
        help=("Name of Brew tag to check for embargoed builds. Default: '%s'" % BREW_EMBARGOED_TAG)
    )
    parser.add_option(
        "--module-builds",
        action="store_true",
        help="to distinguish between module & non-module builds."
    )
    parser.add_option(
        "--quiet",
        action="store_true",
        help="Suppress most logs except critical ones"
    )
    parser.add_option(
        "--verbose",
        action="store_true",
        help="Output VERBOSE lines"
    )
    parser.add_option(
        "--debug",
        action="store_true",
        help="Show debug output"
    )

    opts, _ = parser.parse_args()

    log_level = logging.WARNING # Default logging level
    if opts.quiet:
        log_level = logging.ERROR
    elif opts.verbose:
        log_level = logging.INFO
    elif opts.debug:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level)




    # Disabling all urllib3 warnings to hide all noise caused by old python version
    # on RHEL 6.9 (lack of SNI support and an outdated ssl module).
    # It is not possible to hide specific warnings due to import issues on the server.
    # Refer to JIRA: RCMWORK-5834 for more details
    urllib3.disable_warnings()

    # Checking for valid brew_tag
    koji_proxy = koji.ClientSession(opts.brew_url, opts={'krbservice': 'brewhub'})
    koji_proxy.krb_login()
    multicall = xmlrpclib.MultiCall(koji_proxy)
    errata_proxy = xmlrpclib.ServerProxy(opts.errata_xmlrpc_url)

    test_tags = []

    embargoed_builds = set()
    if not opts.brew_ignore_embargoed_tag:
        multicall.getTag(opts.brew_embargoed_tag_name)
        logging.debug("Getting embargoed builds")
        embargoed_builds = get_brew_builds(koji_proxy, opts.brew_embargoed_tag_name,
                                           latest=False, inherit=False)

    if not opts.brew_pending_tag:
        parser.error("specify brew tag")

    multicall.getTag(opts.brew_pending_tag)
    test_tags.append(opts.brew_pending_tag)

    if not opts.errata_product:
        parser.error("specify errata product")

    if not (opts.errata_group or opts.errata_product_version):
        parser.error("specify errata group (release) or errata product version")

    logging.debug("Getting all builds from tag: %s",
        opts.brew_pending_tag)

    # these are currently in pending
    tagged_builds = get_brew_builds(koji_proxy, opts.brew_pending_tag,
                                    latest=False, inherit=False)

    logging.debug("product: %s release_group: %s product_version: %s",
        opts.errata_product, opts.errata_group, opts.errata_product_version)
    # all of these should be in pending
    all_et_builds = get_errata_builds(errata_proxy, opts.errata_group, opts.errata_product, opts.module_builds,
                    opts.errata_product_version)

    et_builds = set(all_et_builds.keys())

    # Ignore ET builds that don't come from specified source tag(s)
    if opts.brew_source_tag:
        # builds in tags specified via --brew-source-tag opts
        source_tag_builds = set()
        for source_tag in opts.brew_source_tag:
            builds = get_brew_builds(koji_proxy, source_tag,
                                        latest=False, inherit=False)
            source_tag_builds |= set(builds)

        # keep only builds we care about
        et_builds &= source_tag_builds

    # Remove builds that are also in the embargoed build list
    logging.debug("Removing builds which are also in the '%s' tag", opts.brew_embargoed_tag_name)
    et_builds -= set(embargoed_builds)

    logging.debug("Getting builds which are in Errata but not in tag: %s",
        opts.brew_pending_tag)
    missing = get_missing_builds(et_builds, tagged_builds)
    logging.debug("Found %d builds which are not tagged. %s" % (len(missing), missing))

    logging.debug("Getting builds which are in tag: %s but not in Errata",
        opts.brew_pending_tag)
    extra = get_extra_builds(et_builds, tagged_builds)
    logging.debug("Found %d builds which are tagged and shouldn't be. %s" % (len(extra), extra))



    # to be removed from -pending
    tag_builds(koji_proxy, opts.brew_pending_tag, missing, tagged_builds, test=opts.test)
    untag_builds(koji_proxy, opts.brew_pending_tag, extra, tagged_builds, test=opts.test)

if __name__ == "__main__":
    main()

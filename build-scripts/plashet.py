#!/usr/bin/python3

# Requirements
# sudo yum install python3-devel
# pip3 install krb5-workstation krb5-devel
# pip3 install click kobo koji wrapt PyYaml requests_kerberos

import click
import xmlrpc.client as xmlrpclib
import os
import pathlib
import glob
from kobo.rpmlib import parse_nvr, compare_nvr
import koji
import logging
import requests
import ssl
import time
import wrapt
import sys
import yaml

from requests_kerberos import HTTPKerberosAuth
from types import SimpleNamespace
from typing import Dict, List

BREW_URL = "https://brewhub.engineering.redhat.com/brewhub"
ERRATA_URL = "http://errata-xmlrpc.devel.redhat.com/errata/errata_service"
ERRATA_API_URL = "https://errata.engineering.redhat.com/api/v1/"

logger: logging.Logger = None

# As a plashet is assembled, concerns about its viability can be
# added to this list. It will be captured in plashet.yml for easy
# reference.
plashet_concerns = []


def mkdirs(path, mode=0o755):
    """
    Make sure a directory exists. Similar to shell command `mkdir -p`.
    :param path: Str path
    :param mode: create directories with mode
    """
    pathlib.Path(str(path)).mkdir(mode=mode, parents=True, exist_ok=True)


def update_advisory_builds(config, errata_proxy, advisory_id, nvres, nvr_product_version):
    """
    Attempts to get a specific set of RPM nvrs attached to an advisory
    :param errata_proxy: proxy
    :param advisory_id: The advisory to modify (should be in NEW_FILES)
    :param product_version: Product version to attach RPMs for (e.g. RHEL-7-OSE-4.5)
    :param nvres: A list of RPM nvrs
    :param nvr_product_version: A map of nvr->product_version
    :return: n/a
    Exception thrown if there is an error.
    """

    desired_nvrs = set([strip_epoch(n) for n in nvres])
    errata_nvrs = set()
    for build in errata_proxy.getErrataBrewBuilds(advisory_id):
        nvr = build["brew_build_nvr"]
        errata_nvrs.add(nvr)

    to_remove = errata_nvrs.difference(desired_nvrs)
    to_add = desired_nvrs.difference(errata_nvrs)

    logger.info(f'Found currently attached to advisory: {to_remove}')
    logger.info(f'Found not attached to advisory: {to_add}')

    auth = HTTPKerberosAuth()
    for nvr in to_remove:
        remove_nvr_payload = {
            'nvr': nvr,
        }
        res = requests.post(f'{ERRATA_API_URL}/erratum/{advisory_id}/remove_build',
                            verify=ssl.get_default_verify_paths().openssl_cafile,
                            auth=auth,
                            json=remove_nvr_payload,
                            )
        if res.status_code not in (200, 201):
            logger.error(f'Error remove build from advisory: {res.content}')
            raise IOError(f'Unable to remove nvr from advisory {advisory_id}: {nvr}')

    add_builds_payload = []
    for nvr in to_add:
        parsed_nvr = parse_nvr(nvr)
        package_name = parsed_nvr["name"]

        if package_name in config.exclude_package:
            logger.info(f'Skipping advisory attach for excluded package: {nvr}')
            continue

        add_builds_payload.append({
            "product_version": nvr_product_version[nvr],
            "build": nvr,
            "file_types": ['rpm']
        })

    if add_builds_payload:
        res = requests.post(f'{ERRATA_API_URL}/erratum/{advisory_id}/add_builds',
                            verify=ssl.get_default_verify_paths().openssl_cafile,
                            auth=HTTPKerberosAuth(),
                            json=add_builds_payload,
                            )

        if res.status_code not in (201, 200):
            logger.error(f'Error attaching builds to advisory')
            logger.error(f'Request: {add_builds_payload}')
            logger.error(f'Response {res.status_code}: {res.content}')
            raise IOError(f'Unable to add nvrs to advisory {advisory_id}: {to_add}')


def _assemble_repo(config, nvres: List[str]):
    """
    This method is intended to be wrapped by assemble_repo.
    Assembles one or more architecture specific repos in the
    dest_dir with the specified nvrs. It is expected by the time this method
    is called that all RPMs are signed if any of those arches requires signing.
    :param config: cli config
    :param nvres: a list of nvres to include.
    :return: n/a
    An exception will be thrown if no RPMs can be found matching an nvr.
    """

    for arch_name, signing_mode in config.arch:
        # These directories shouldn't exist yet. They will be created during assemble.
        dest_arch_path = os.path.join(config.dest_dir, arch_name)
        if config.repo_subdir:
            dest_arch_path += '/' + config.repo_subdir.strip('/')  # strip / from start and end
        links_dir = os.path.join(dest_arch_path, 'Packages')
        rpm_list_path = os.path.join(dest_arch_path, 'rpm_list')
        mkdirs(links_dir)

        # Each arch will have its own yum repo & thus needs its own rpm_list
        with open(rpm_list_path, mode='w+') as rl:

            for nvre in nvres:
                nvr = strip_epoch(nvre)
                matched_count = 0

                nvre_obj = parse_nvr(nvre)
                package_name = nvre_obj["name"]

                if package_name in config.exclude_package:
                    logger.info(f'Skipping repo addition for excluded package: {nvre}')
                    continue

                signed = (signing_mode == 'signed')
                br_arch_base_path = get_brewroot_arch_base_path(config, nvre, signed)

                # Include noarch in each arch specific repo.
                include_arches = [arch_name, 'noarch']
                for a in include_arches:
                    brewroot_arch_path = os.path.join(br_arch_base_path, a)

                    if not os.path.isdir(brewroot_arch_path):
                        logger.debug(f'No {a} arch directory for {nvre}')
                        continue

                    logger.info(f'Found {"signed" if signed else "unsigned"} {a} arch directory for {nvre}')
                    link_name = '{nvr}__{arch}'.format(
                        nvr=nvr,
                        arch=a,
                    )
                    if signed:
                        link_name += f'__{config.signing_key_id}'

                    package_link_path = os.path.join(links_dir, link_name)
                    os.symlink(brewroot_arch_path, package_link_path)

                    rpms = os.listdir(package_link_path)
                    if not rpms:
                        raise IOError(f'Did not find any rpms in {brewroot_arch_path}')

                    for r in rpms:
                        rpm_path = os.path.join('Packages', link_name, r)
                        rl.write(rpm_path + '\n')
                        matched_count += 1

                if not matched_count:
                    logger.warning("Unable to find any {arch} rpms for {nvre} in {p} ; this may be ok if the package doesn't support the arch and it is not required for that arch".format(
                                       arch=arch_name, nvre=nvre, p=get_brewroot_arch_base_path(config, nvre, signed)))

        if os.system('cd {repo_dir} && createrepo_c -i rpm_list .'.format(repo_dir=dest_arch_path)) != 0:
            raise IOError('Error creating repo at: {repo_dir}'.format(repo_dir=dest_arch_path))

        print('Successfully created repo at: {repo_dir}'.format(repo_dir=dest_arch_path))


def assemble_repo(config, nvres, event_info=None, extra_data: Dict = None):
    """
    Assembles one or more architecture specific repos in the
    dest_dir with the specified nvrs. It is expected by the time this method
    is called that all RPMs are signed if any of those arches requires signing.
    :param config: cli config
    :param nvres: a list of nvres to include.
    :param event_info: The brew event information to encode into the plashet.yml
    :param extra_data: a dictionary of data that will be added to the plashet.yml file
        if the repo is successfully assembled.
    :return: n/a
    An exception will be thrown if no RPMs can be found matching an nvr.
    """
    koji_proxy = KojiWrapper(koji.ClientSession(config.brew_url, opts={'krbservice': 'brewhub'}))

    with open(os.path.join(config.dest_dir, 'plashet.yml'), mode='w+', encoding='utf-8') as y:
        success = False
        try:
            _assemble_repo(config, nvres)
            success = True
        finally:

            packages = list()
            for nvre in sorted(nvres):
                nvr = strip_epoch(nvre)
                build = koji_proxy.getBuild(nvr)
                tag_listing = koji_proxy.queryHistory(table='tag_listing',
                                                      build=build['id'])['tag_listing']
                latest_tag = {}
                if tag_listing:
                    tag_listing.sort(key=lambda event: event['create_event'])
                    tl = tag_listing[-1]
                    latest_tag = {
                        'tag_name': tl['tag.name'],
                        'event': tl['create_event'],
                    }

                package = {
                    'package_name': build['package_name'],
                    'build_id': build['id'],
                    'nvr': build['nvr'],
                    'epoch': build['epoch'],
                    'latest_tag': latest_tag,
                }
                packages.append(package)

            plashet_info = {
                'assemble': {
                    'success': success,
                    'concerns': plashet_concerns,
                    'brew_event': event_info or koji_proxy.getLastEvent(),
                    'packages': packages,
                },
                'extra': extra_data or {},
            }
            yaml.dump(plashet_info, y, default_flow_style=False)


def get_brewroot_arch_base_path(config, nvre, signed):
    """
    :param config: Base cli config object
    :param nvre: Will return the base directory under which the arch directories should exist.
    :param signed: If True, the base directory under which signed arch directories should exit.
    An exception will be raised if the nvr cannot be found unsigned in the brewroot as this
    indicates the nvr has not been built.
    """
    parsed_nvr = parse_nvr(nvre)
    package_name = parsed_nvr["name"]
    package_version = parsed_nvr["version"]
    package_release = parsed_nvr["release"]

    unsigned_arch_base_path = '{brew_packages}/{package_name}/{package_version}/{package_release}'.format(
            brew_packages=config.packages_path,
            package_name=package_name,
            package_version=package_version,
            package_release=package_release,
    )

    if not os.path.isdir(unsigned_arch_base_path):
        raise IOError(f'Unable to find {nvre} in brewroot filesystem: {unsigned_arch_base_path}')

    if not signed:
        return unsigned_arch_base_path
    else:
        return '{unsigned_arch_path}/data/signed/{signing_key_id}'.format(
            unsigned_arch_path=unsigned_arch_base_path,
            signing_key_id=config.signing_key_id,
        )


def is_signed(config, nvre):
    """
    :param config: cli config object
    :param nvre: The nvr to check
    :return: Returns whether the specified nvr is signed with the signing key id. An exception
    will be raise if the nvr can't be found at all in the brew root (i.e. unsigned can't be found).
    """
    signed_base = get_brewroot_arch_base_path(config, nvre, True)
    unsigned_base = get_brewroot_arch_base_path(config, nvre, False)

    if os.path.isdir(signed_base):
        # The signed directory exists, but we also want to make sure that the RPM counts match
        # the unsigned directories. This eliminates a potential race condition between a nvr
        # being signed and the time it takes to populate the brewroot directories.

        signed_rpm_count = len(glob.glob(f'{signed_base}/**/*.rpm', recursive=True))
        # Note the structure brewroot has signed under the unsigned directory, so subtract the
        # signed from the unsigned.
        unsigned_rpm_count = len(set(glob.glob(f'{unsigned_base}/**/*.rpm', recursive=True)) - set(glob.glob(f'{unsigned_base}/data/**/*.rpm', recursive=True)))

        if unsigned_rpm_count != signed_rpm_count:
            logger.info(f'Found incomplete signed rpm directory for {nvre}; brewroot may still be being built.')
            return False
        return True
    else:
        return False


def signed_desired(config):
    """
    :param config: The cli config.
    :return: Returns True if any of the arches specified on the command line require signing.
    """
    for a, mode in config.arch:
        if mode == 'signed':
            return True
        if mode != 'unsigned':
            raise IOError(f'Unexpected signing mode for arch {a} (must be signed or unsigned): {mode}')


def strip_epoch(nvr: str):
    """
    If an NVR string is N-V-R:E, returns only the NVR portion. Otherwise
    returns NVR exactly as-is.
    """
    return nvr.split(':')[0]


def to_nvre(build_record):
    """
    From a build record object (such as an entry returned by listTagged),
    returns the full nvre in the form n-v-r:E.
    """
    nvr = build_record['nvr']
    if 'epoch' in build_record and build_record["epoch"] and build_record["epoch"] != 'None':
        return f'{nvr}:{build_record["epoch"]}'
    return nvr


def assert_signed(config, nvre, poll_for=15):
    """
    Raises an exception if the nvr has not been specified by the config signing key.
    :param config: The cli config
    :param nvre: The nvr to check.
    :param poll_for: The number of minutes to continue checking until an exception is raised.
    :return: number of minutes used for polling during successful wait for signing
    """
    time_used = 0

    while not is_signed(config, nvre):
        if poll_for <= 0:
            br_arch_base_path = get_brewroot_arch_base_path(config, nvre, True)
            logger.info('Package {nvre} has not been signed; {signed_path} does not exist'.format(
                nvre=nvre,
                signed_path=br_arch_base_path,
            ))
            raise IOError('Package {nvre} has not been signed; {signed_path} does not exist'.format(
                nvre=nvre,
                signed_path=br_arch_base_path,
            ))
        print(f'Waiting for up to {poll_for} more minutes')
        poll_for -= 1
        time_used += 1
        time.sleep(60)
    return time_used


def setup_logging(dest_dir: str):
    """
    Initializes the root logger to write a log into the plashet directory as well as
    stream output to stderr.
    :param dest_dir: The directory in which to create the log.
    """
    global logger
    mkdirs(dest_dir)
    logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger('plashet')
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(os.path.join(dest_dir, 'plashet.log'), mode='w+')
    fh.setLevel(logging.DEBUG)
    # create console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info('Invocation: ' + ' '.join(sys.argv))


@click.group()
@click.pass_context
@click.option('--base-dir', default=os.getcwd(),
              help='Parent directory for repo directory. Defaults to current working directory.')
@click.option('--name', metavar='NAME', required=True, help='Directory name to create relative to base directory.')
@click.option('--repo-subdir', metavar='REL_PATH', required=False, help='Directory under each arch repo to create yum repo (e.g. "os" will create x86_64/os/repodata)')
@click.option('--signing-key-id', required=False, metavar='HEX',
              help='Signing key to require for signed arches if you fd431d51 is not desired.')
@click.option('--arch', multiple=True, metavar='ARCH <signed|unsigned>',
              required=True, nargs=2,
              help='For each arch to include in the plashet. Each arch will be a repo beneath the plashet dir.')
@click.option('--errata-xmlrpc-url', default=ERRATA_URL, help='The errata xmlrpmc url')
@click.option('--brew-root', metavar='PATH', default='/mnt/redhat/brewroot', help='Filesystem location of brew root')
@click.option('--brew-url', metavar='URL', default=BREW_URL, help='Override default brew API url')
@click.option('-x', '--exclude-package', metavar='NAME',
              multiple=True, default=[], help='Exclude one or more package names')
@click.option('-i', '--include-package', metavar='NAME',
              multiple=True, default=[], help='Only include specified packages')
def cli(ctx, base_dir, brew_root, name, signing_key_id, **kwargs):
    """
    Creates a directory containing one or more arch specific yum repositories by using local
    symlinks to a brewroot filesystem location. This avoids network transfer time.

    If you need to transfer the resultant repo to a mirror which does not have a
    brewroot (e.g. the openshift mirrors), using rsync --copy-links. If you are transferring
    the repo to a system with a brewroot filesystem (e.g. rcm-guest), preserve the
    links (using --links) and the transfer should be extremely quick.

    You must specify one or more --arch parameters. For each architecture, you can
    request that it contain signed or unsigned RPMs in the result arch repository.

    \b
    Example invocations:
    $ ./plashet.py
        --base-dir /some/base/dir --name my_plashet
        --repo-subdir os
        --arch x86_64 signed  --arch s390x unsigned
        from-tags --include-embargoed -t rhaos-4.4-rhel-7-candidate RHEL-7-OSE-4.4 --signing-advisory-id 54765

        \b
        This preceding command will make:
            /some/base/dir/my_plashet/x86_64/os  - with signed RPMs (any unsigned RPMs will be signed using 54765)
            and
            /some/base/dir/my_plashet/xs390x/os  - with unsigned RPMs

    \b
    $ ./plashet.py
        --name my_repo
        --arch x86_64 unsigned  --arch s390x unsigned
        from-advisories --advisory-id 54701
    """

    brew_root_path = os.path.abspath(brew_root)
    packages_path = os.path.join(brew_root_path, 'packages')
    if not os.path.isdir(packages_path):
        print('{} does not exist; unable to start'.format(packages_path))
        exit(1)

    base_dir_path = os.path.abspath(base_dir)
    mkdirs(base_dir_path)

    dest_dir = os.path.join(base_dir_path, name)
    if os.path.exists(dest_dir):
        print('Destination {} already exists; name must be unique'.format(dest_dir))
        exit(1)

    setup_logging(dest_dir)

    ctx.obj = SimpleNamespace(base_dir=base_dir,
                              brew_root=brew_root,
                              name=name,
                              brew_root_path=brew_root_path,
                              packages_path=packages_path,
                              base_dir_path=base_dir_path,
                              dest_dir=dest_dir,
                              signing_key_id=signing_key_id if signing_key_id else 'fd431d51',
                              **kwargs)


class KojiWrapper(wrapt.ObjectProxy):
    """
    We've seen the koji client occasionally get
    Connection Reset by Peer errors.. "requests.exceptions.ConnectionError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))"
    Under the theory that these operations just need to be retried,
    this wrapper will automatically retry all invocations of koji APIs.
    """

    def __call__(self, *args, **kwargs):
        retries = 4
        while retries > 0:
            try:
                return self.__wrapped__(*args, **kwargs)
            except requests.exceptions.ConnectionError as ce:
                time.sleep(5)
                retries -= 1
                if retries == 0:
                    raise ce


@cli.command('from-tags', short_help='Collects a set of RPMs from specified brew tags -- signing if necessary.')
@click.pass_obj
@click.option('-t', '--brew-tag', multiple=True, required=True, nargs=2, help='One or more brew tags whose RPMs should be included in the repo; format is: <tag> <product_version>')
@click.option('-e', '--embargoed-brew-tag', multiple=True, required=False, help='If specified, any nvr found in these tags will be considered embargoed (unless they have already shipped)')
@click.option('--embargoed-nvr', multiple=True, required=False, help='Treat this nvr as embargoed (unless it has already shipped)')
@click.option('--signing-advisory-id', required=False, help='Use this auto-signing advisory to sign RPMs if necessary.')
@click.option('--signing-advisory-mode', required=False, default="clean", type=click.Choice(['leave', 'clean'], case_sensitive=False),
              help='clean=remove all builds on start and successful exit; leave=leave existing builds attached when attempting to sign')
@click.option('--poll-for', default=15, type=click.INT, help='Allow up to this number of minutes for auto-signing')
@click.option('--include-previous-for', multiple=True, metavar='PACKAGE_NAME_PREFFIX', required=False, help='For specified package (may be package name prefix), include latest-1 tagged nvr in the plashet')
@click.option('--include-previous', default=False, is_flag=True,
              help='Like --include-previous-for, but performs the operation for all packages found in the tags')
@click.option('--event', required=False, default=None, help='The brew event for the desired tag states')
@click.option('--include-embargoed', default=False, is_flag=True,
              help='If specified, embargoed/unshipped RPMs will be included in the plashet')
@click.option('--inherit', required=False, default=False, is_flag=True,
              help='Descend into brew tag inheritance')
def from_tags(config, brew_tag, embargoed_brew_tag, embargoed_nvr, signing_advisory_id, signing_advisory_mode,
              poll_for, include_previous_for, include_previous, event, include_embargoed, inherit):
    """
    The repositories are filled with RPMs derived from the list of
    brew tags. If the RPMs are not signed and a repo should contain signed content,
    the specified advisory will be used for signing the RPMs (requires
    automatic sign on attach).

    If you specify --embargoed-brew-tag, plashet will treat any nvr found in this tag as if it is
    embargoed (unless has already shipped). This is useful since the .p1 convention cannot be used
    on RPMs not built by ART.


    \b
    --brew-tag <tag> <product_version> example: --brew-tag rhaos-4.5-rhel-8-candidate OSE-4.5-RHEL-8 --brew-tag .. ..
    """

    koji_proxy = KojiWrapper(koji.ClientSession(config.brew_url, opts={'krbservice': 'brewhub'}))
    errata_proxy = xmlrpclib.ServerProxy(config.errata_xmlrpc_url)

    if event:
        event = int(event)
        event_info = koji_proxy.getEvent(event)
    else:
        # If none was specified, lock in an event so that there are no race conditions with
        # packages changing while we run.
        event_info = koji_proxy.getLastEvent()
        event = event_info['id']

    # Gather up all nvrs tagged in the embargoed brew tags into a set.
    embargoed_tag_nvrs = set()
    embargoed_tag_nvrs.update(embargoed_nvr)
    for ebt in embargoed_brew_tag:
        for build in koji_proxy.listTagged(ebt, latest=False, inherit=False, event=event, type='rpm'):
            embargoed_tag_nvrs.add(to_nvre(build))
    logger.info('Will treat the following nvrs as potentially embargoed: {}'.format(embargoed_tag_nvrs))

    actual_embargoed_nvres = list()  # A list of nvres detected as embargoed
    desired_nvres = set()
    historical_nvres = set()
    nvr_product_version = {}
    for tag, product_version in brew_tag:

        released_package_nvre_obj = {}  # maps released package names to the most recently released package nvr object (e.g { 'name': ...,  }
        if tag.endswith('-candidate'):
            """
            So here's the thing. If you ship a version of a package 1.16.6 via errata tool, 
            it will prevent you from shipping an older version of that package (e.g. 1.16.2) or even
            attaching it to an errata. This prevents us from auto-signing the older package. Since it
            is just invalid, we need to find the latest version of packages which have shipped
            and make sure plashet filters out anything that is older before signing/building.
            
            Without this filtering, the error from errata tool looks like:
            b'{"error":"Unable to add build \'cri-o-1.16.6-2.rhaos4.3.git4936f44.el7\' which is older than cri-o-1.16.6-16.dev.rhaos4.3.git4936f44.el7"}'
            """
            released_tag = tag[:tag.index('-candidate')]
            for build in koji_proxy.listTagged(released_tag, latest=True, inherit=True, event=event, type='rpm'):
                package_name = build['package_name']
                released_package_nvre_obj[package_name] = parse_nvr(to_nvre(build))

        for build in koji_proxy.listTagged(tag, latest=True, inherit=inherit, event=event, type='rpm'):
            package_name = build['package_name']
            nvre = to_nvre(build)
            nvre_obj = parse_nvr(nvre)

            released_nvre_obj = None  # if the package has shipped before, the parsed nvr of the most recently shipped
            if package_name in released_package_nvre_obj:
                released_nvre_obj = released_package_nvre_obj[package_name]

            def is_embargoed(an_nvre):
                # .p1 or inclusion in the embargoed_tag_nvrs indicates this rpm is embargoed OR *was* embargoed.
                # We can ignore it if it has already shipped.
                test_nvre_obj = parse_nvr(an_nvre)
                if released_nvre_obj is None or compare_nvr(test_nvre_obj, released_nvre_obj) > 0:  # If this nvr hasn't shipped
                    if '.p1' in an_nvre or strip_epoch(an_nvre) in embargoed_tag_nvrs:  # It's embargoed!
                        return True
                return False

            if package_name in config.exclude_package:
                logger.info(f'Skipping tagged but command line excluded package: {nvre}')
                continue

            if config.include_package and package_name not in config.include_package:
                logger.info(f'Skipping tagged but not command line included package: {nvre}')
                continue

            if is_embargoed(nvre):
                # An embargoed build has not been shipped.
                actual_embargoed_nvres.append(nvre)  # Record that at the time of build, this was considered embargoed

                if not include_embargoed:
                    # We are being asked to build a plashet without embargoed RPMs. We need to find a stand-in.
                    # Search through the tag's package history to find the last build that was NOT embargoed.
                    unembargoed_nvre = None
                    for build in koji_proxy.listTagged(tag, package=package_name, inherit=True, event=event, type='rpm'):
                        test_nvre = to_nvre(build)
                        if is_embargoed(test_nvre):
                            continue
                        unembargoed_nvre = test_nvre
                        break

                    if unembargoed_nvre is None:
                        raise IOError(f'Unable to build unembargoed plashet. Lastest build of {package_name} ({nvre}) is embargoed but unable to find unembargoed version in history')
                    plashet_concerns.append(f'Swapping embargoed nvr {nvre} for unembargoed nvr {unembargoed_nvre}.')
                    logger.info(plashet_concerns[-1])
                    nvre = unembargoed_nvre

            if released_nvre_obj:
                if compare_nvr(nvre_obj, released_nvre_obj) < 0:  # if the current nvr is less than the released NVR
                    msg = f'Skipping tagged {nvre} because it is older than a released version: {released_nvre_obj}'
                    plashet_concerns.append(msg)
                    logger.error(msg)
                    continue

            logger.info(f'{tag} contains package: {nvre}')
            desired_nvres.add(nvre)
            nvr_product_version[strip_epoch(nvre)] = product_version

            if package_name.startswith(tuple(include_previous_for)) or include_previous:
                # The user has asked for non-latest entry for this package to be included in the plashet.
                # we can try to find this by looking at the packages full history in this tag. Listing is
                # newest -> oldest tagging event for this tag/package combination.

                tag_history = koji_proxy.listTagged(tag, package=package_name, inherit=True, event=event, type='rpm')
                tracking = False  # There may have been embargo shenanigans above; so we can't assume [0] is our target nvr
                for htag in tag_history:
                    history_nvre = to_nvre(htag)
                    if history_nvre == nvre:
                        # We've found the target NVR in the list. Everything that follows can be considered for history.
                        tracking = True
                        continue
                    if not tracking:
                        # Haven't found our target NVR yet; so we can't consider this entry for history.
                        continue
                    history_nvre_obj = parse_nvr(history_nvre)
                    if compare_nvr(history_nvre_obj, nvre_obj) > 0:
                        # Is our historical nvr > target for inclusion in plashet? If it is, a user of the plashet would
                        # pull in the historical nvr with a yum install. We can't allow that. Just give up -- this is
                        # not in line with the use case of history.
                        plashet_concerns.append(f'Unable to include previous for {package_name} because history {history_nvre} is newer than latest tagged {nvre}')
                        break
                    if include_embargoed is False and is_embargoed(history_nvre):
                        # smh.. history is still under embargo. What you are guys doing?!
                        plashet_concerns.append(f'Unable to include previous for {package_name} because history {history_nvre} is under embargo')
                        break
                    historical_nvres.add(history_nvre)
                    nvr_product_version[strip_epoch(history_nvre)] = product_version
                    break

    if config.include_package and len(config.include_package) != len(desired_nvres):
        raise IOError(f'Did not find all command line included packages {config.include_package}; only found {desired_nvres}')

    # Did any of the arches require signed content?
    possible_signing_needed = signed_desired(config)

    if possible_signing_needed:
        logger.info(f'At least one architecture requires signed nvres')

        # Each set must be attached separately because you cannot attach two nvres of the same
        # package to an errata at the same time.
        for set_name, nvre_set in {'latest_tagged': desired_nvres, 'previous_tagged': historical_nvres}.items():
            if not nvre_set:
                logger.info(f'NVRE set {set_name} is empty; nothing to sign')
                continue

            if signing_advisory_id:
                # Remove all builds attached to advisory before attempting signing
                update_advisory_builds(config, errata_proxy, signing_advisory_id, [], nvr_product_version)
                nvres_for_advisory = []

                for nvre in nvre_set:
                    if not is_signed(config, nvre):
                        logger.info(f'Found an unsigned nvr in nvre set {set_name} (will attempt to sign): {nvre}')
                        nvres_for_advisory.append(nvre)

                logger.info(f'Updating advisory to get nvre set {set_name} signed: {signing_advisory_id}')
                update_advisory_builds(config, errata_proxy, signing_advisory_id, nvres_for_advisory, nvr_product_version)

            else:
                logger.warning(f'No signing advisory specified; will simply poll and hope for nvre set {set_name}')

            # Whether we've attached to advisory or no, wait until signing require is met
            # or throw exception on timeout.
            logger.info(f'Waiting for all nvres in set {set_name} to be signed..')
            for nvre in desired_nvres:
                poll_for -= assert_signed(config, nvre)

    if signing_advisory_id and signing_advisory_mode == 'clean':
        # Seems that everything is signed; remove builds from the advisory.
        update_advisory_builds(config, errata_proxy, signing_advisory_id, [], nvr_product_version)

    extra_embargo_info = {  # Data related to embargoes that will be written into the plashet.yml
        'embargoed_permitted': include_embargoed,  # Whether we included or excluded these nvrs in the plashet
        'detected_as_embargoed': actual_embargoed_nvres,
    }

    extra_data = {  # Data that will be included in the plashet.yml after assembly.
        'embargo_info': extra_embargo_info,
        'included_previous_nvrs': list(historical_nvres),
    }

    all_nvres = set()
    all_nvres.update(desired_nvres)
    all_nvres.update(historical_nvres)
    assemble_repo(config, all_nvres, event_info, extra_data=extra_data)


@cli.command('from-images', short_help='Collects a set of RPMs attached to specified advisories.')
@click.pass_obj
@click.option('--image', 'images', metavar='IMAGE_NVR', multiple=True, required=True, help='Image NVRs which contain RPMs to include in the plashet [multiple].')
@click.option('--replace', multiple=True, metavar='RPM_PACKAGE_NVR', required=False, help='Include or override the package NVR used in the image(s) with this package version.')
@click.option('-t', '--brew-tag', multiple=True, required=False, nargs=2, help='One or more brew tags which will be used to sign RPMs required by this plashet: <tag> <product_version>')
@click.option('--signing-advisory-id', required=False, help='Use this auto-signing advisory to sign RPMs if necessary.')
@click.option('--poll-for', default=15, type=click.INT, help='Allow up to this number of minutes for auto-signing')
def from_images(config, images, replace, brew_tag, signing_advisory_id, poll_for):
    """
    Creates a directory containing arch specific yum repository subdirectories based on RPMs
    used within a specific set of existing brew-built images.

    To override a specific RPM package within the specified images, use --replace. The NVR
    will be included in the plashet instead of the version in the images.

    If the package is not found within an image, --replace will still cause the NVR to be
    included in the final plashet.

    In order to sign a 'replace' package that is not already signed, specify brew-tags that
    package have been tagged with. If a package has been tagged before and is unsigned,
    the signing advisory will be used.
    """

    koji_proxy = KojiWrapper(koji.ClientSession(config.brew_url, opts={'krbservice': 'brewhub'}))
    errata_proxy = xmlrpclib.ServerProxy(config.errata_xmlrpc_url)

    package_nvrs: Dict[str, str] = dict()  # maps package name to nvr

    replaced = set()
    sign_using: Dict[str,List[str]] = {}  # Maps production version to the nvrs it should be used to sign
    for nvr in replace:
        package_build = koji_proxy.getBuild(nvr)
        if not package_build:
            raise IOError(f'Did not find build for replacement package NVR: {nvr}')
        package_name = package_build['package_name']
        package_nvrs[package_name] = nvr
        replaced.add(package_name)

        if not is_signed(config, nvr):
            # For the signing part of the work, bucket each unsigned NVR into
            # a product that can potentially sign it.
            for tag, product_version in brew_tag:
                if koji_proxy.listTagged(tag, package=package_name):
                    if product_version not in sign_using:
                        nvr_list: List[str] = list()
                        sign_using[product_version] = nvr_list
                    else:
                        nvr_list = sign_using[product_version]
                    nvr_list.append(nvr)

    if signed_desired(config):
        # Let's see if the any of the --replace NVRs need to be signed before
        # building the plashet.
        logger.info(f'At least one architecture requires signed nvres')

        if signing_advisory_id:
            for product_version, nvr_list in sign_using.items():
                logger.info(f'Attempting to sign {nvr_list} using product: {product_version} and advisory {signing_advisory_id}')
                # Remove all builds attached to advisory before attempting signing
                update_advisory_builds(config, errata_proxy, signing_advisory_id, [],
                                       product_version)
                update_advisory_builds(config, errata_proxy, signing_advisory_id, nvr_list,
                                       product_version)
        else:
            logger.warning(f'No signing advisory specified; will poll for any unsigned NVRs')

        # Whether we've attached to advisory or no, wait until signing require is met
        # or throw exception on timeout.
        logger.info(f'Waiting for all nvre in set {replace} to be signed..')
        for nvr in replace:
            poll_for -= assert_signed(config, nvr)

    for image_nvr in images:
        image_build = koji_proxy.getBuild(image_nvr)
        archives = koji_proxy.listArchives(image_build['id'])

        build_cache: Dict[str, Dict] = dict()  # Maps build_id to build object from brew
        for archive in archives:
            # Example results of listing RPMs in an given imageID:
            # https://gist.github.com/jupierce/a8798858104dcf6dfa4bd1d6dd99d2d8
            archive_id = archive['id']
            rpm_entries = koji_proxy.listRPMs(imageID=archive_id)
            for rpm_entry in rpm_entries:
                build_id = rpm_entry['build_id']

                # Multiple RPMs might be from the same build and multiple images may use
                # the same build. Cache results to prevent unnecessary queries.
                if build_id in build_cache:
                    build = build_cache[build_id]
                else:
                    build = koji_proxy.getBuild(build_id)
                    build_cache[build_id] = build

                package_name = build['package_name']
                if package_name in replaced:
                    continue

                nvr = build['nvr']
                if package_name in package_nvrs and package_nvrs[package_name] != nvr:
                    raise IOError(f'Images contain inconsistent versions of {package_name}: {nvr} vs {package_nvrs[package_name]} . You must explicitly resolve this with --replace.')

                package_nvrs[package_name] = nvr

    nvrs = package_nvrs.values()
    assemble_repo(config, nvrs)


@cli.command('from-advisories', short_help='Collects a set of RPMs attached to specified advisories.')
@click.pass_obj
@click.option('-a', '--advisory-id', multiple=True, required=True, help='Advisories to check')
@click.option('--poll-for', default=0, type=click.INT, help='Allow up to this number of minutes for signing')
@click.option('--module-builds', default=False)
def from_advisories(config, advisory_id, module_builds, poll_for):
    """
    Creates a directory containing arch specific yum repository subdirectories based on RPMs
    attached to one or more advisories.
    """
    errata_proxy = xmlrpclib.ServerProxy(config.errata_xmlrpc_url)

    nvrs = set()
    for id in advisory_id:
        # https://gist.github.com/jupierce/7157d5620b7eb218f73542b3f9fec305
        for build in errata_proxy.getErrataBrewBuilds(id):
            nvr = build["brew_build_nvr"]
            is_module = build["is_module"]

            if module_builds and not is_module:
                continue

            if not module_builds and is_module:
                continue

            if signed_desired(config):
                poll_for -= assert_signed(config, nvr, poll_for=poll_for)

            nvrs.add(nvr)

    assemble_repo(config, nvrs)


if __name__ == '__main__':
    cli()

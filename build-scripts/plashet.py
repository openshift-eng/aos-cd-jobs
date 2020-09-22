#!/usr/bin/python3

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


def update_advisory_builds(config, errata_proxy, advisory_id, nvrs, nvr_product_version):
    """
    Attempts to get a specific set of RPM nvrs attached to an advisory
    :param errata_proxy: proxy
    :param advisory_id: The advisory to modify (should be in NEW_FILES)
    :param product_version: Product version to attach RPMs for (e.g. RHEL-7-OSE-4.5)
    :param nvrs: A list of RPM nvrs
    :param nvr_product_version: A map of nvr->product_version
    :return: n/a
    Exception thrown if there is an error.
    """
    desired_nvrs = set(nvrs)
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


def _assemble_repo(config, nvrs: List[str]):
    """
    This method is intended to be wrapped by assemble_repo.
    Assembles one or more architecture specific repos in the
    dest_dir with the specified nvrs. It is expected by the time this method
    is called that all RPMs are signed if any of those arches requires signing.
    :param config: cli config
    :param nvrs: a list of nvrs to include.
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

            for nvr in nvrs:
                matched_count = 0

                parsed_nvr = parse_nvr(nvr)
                package_name = parsed_nvr["name"]

                if package_name in config.exclude_package:
                    logger.info(f'Skipping repo addition for excluded package: {nvr}')
                    continue

                signed = (signing_mode == 'signed')
                br_arch_base_path = get_brewroot_arch_base_path(config, nvr, signed)

                # Include noarch in each arch specific repo.
                include_arches = [arch_name, 'noarch']
                for a in include_arches:
                    brewroot_arch_path = os.path.join(br_arch_base_path, a)

                    if not os.path.isdir(brewroot_arch_path):
                        logger.debug(f'No {a} arch directory for {nvr}')
                        continue

                    logger.info(f'Found {"signed" if signed else "unsigned"} {a} arch directory for {nvr}')
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
                    logger.warning("Unable to find any {arch} rpms for {nvr} in {p} ; this may be ok if the package doesn't support the arch and it is not required for that arch".format(
                                       arch=arch_name, nvr=nvr, p=get_brewroot_arch_base_path(config, nvr, signed)))

        if os.system('cd {repo_dir} && createrepo -i rpm_list .'.format(repo_dir=dest_arch_path)) != 0:
            raise IOError('Error creating repo at: {repo_dir}'.format(repo_dir=dest_arch_path))

        print('Successfully created repo at: {repo_dir}'.format(repo_dir=dest_arch_path))


def assemble_repo(config, nvrs, event_info=None, extra_data: Dict = None):
    """
    Assembles one or more architecture specific repos in the
    dest_dir with the specified nvrs. It is expected by the time this method
    is called that all RPMs are signed if any of those arches requires signing.
    :param config: cli config
    :param nvrs: a list of nvrs to include.
    :param event_info: The brew event information to encode into the plashet.yml
    :param extra_data: a dictionary of data that will be added to the plashet.yml file
        if the repo is successfully assembled.
    :return: n/a
    An exception will be thrown if no RPMs can be found matching an nvr.
    """
    koji_proxy = KojiWrapper(koji.ClientSession(config.brew_url, opts={'krbservice': 'brewhub', 'serverca': '/etc/pki/brew/legacy.crt'}))
    koji_proxy.gssapi_login()

    with open(os.path.join(config.dest_dir, 'plashet.yml'), mode='w+', encoding='utf-8') as y:
        success = False
        try:
            _assemble_repo(config, nvrs)
            success = True
        finally:
            plashet_info = {
                'assemble': {
                    'success': success,
                    'concerns': plashet_concerns,
                    'brew_event': event_info or koji_proxy.getLastEvent()
                },
                'extra': extra_data or {},
            }
            yaml.dump(plashet_info, y, default_flow_style=False)


def get_brewroot_arch_base_path(config, nvr, signed):
    """
    :param config: Base cli config object
    :param nvr: Will return the base directory under which the arch directories should exist.
    :param signed: If True, the base directory under which signed arch directories should exit.
    An exception will be raised if the nvr cannot be found unsigned in the brewroot as this
    indicates the nvr has not been built.
    """
    parsed_nvr = parse_nvr(nvr)
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
        raise IOError(f'Unable to find {nvr} in brewroot filesystem: {unsigned_arch_base_path}')

    if not signed:
        return unsigned_arch_base_path
    else:
        return '{unsigned_arch_path}/data/signed/{signing_key_id}'.format(
            unsigned_arch_path=unsigned_arch_base_path,
            signing_key_id=config.signing_key_id,
        )


def is_signed(config, nvr):
    """
    :param config: cli config object
    :param nvr: The nvr to check
    :return: Returns whether the specified nvr is signed with the signing key id. An exception
    will be raise if the nvr can't be found at all in the brew root (i.e. unsigned can't be found).
    """
    signed_base = get_brewroot_arch_base_path(config, nvr, True)
    unsigned_base = get_brewroot_arch_base_path(config, nvr, False)

    if os.path.isdir(signed_base):
        # The signed directory exists, but we also want to make sure that the RPM counts match
        # the unsigned directories. This eliminates a potential race condition between a nvr
        # being signed and the time it takes to populate the brewroot directories.

        signed_rpm_count = len(glob.glob(f'{signed_base}/**/*.rpm', recursive=True))
        # Note the structure brewroot has signed under the unsigned directory, so subtract the
        # signed from the unsigned.
        unsigned_rpm_count = len(set(glob.glob(f'{unsigned_base}/**/*.rpm', recursive=True)) - set(glob.glob(f'{unsigned_base}/data/**/*.rpm', recursive=True)))

        if unsigned_rpm_count != signed_rpm_count:
            logger.info(f'Found incomplete signed rpm directory for {nvr}; brewroot may still be being built.')
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


def assert_signed(config, nvr, poll_for=15):
    """
    Raises an exception if the nvr has not been specified by the config signing key.
    :param config: The cli config
    :param nvr: The nvr to check
    :param poll_for: The number of minutes to continue checking until an exception is raised.
    :return: number of minutes used for polling during successful wait for signing
    """
    time_used = 0
    while not is_signed(config, nvr):
        if poll_for <= 0:
            br_arch_base_path = get_brewroot_arch_base_path(config, nvr, True)
            logger.info('Package {nvr} has not been signed; {signed_path} does not exist'.format(
                nvr=nvr,
                signed_path=br_arch_base_path,
            ))
            raise IOError('Package {nvr} has not been signed; {signed_path} does not exist'.format(
                nvr=nvr,
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
    logging.basicConfig(level=logging.DEBUG, filename=os.path.join(dest_dir, 'plashet.log'), filemode='w+')
    logger = logging.getLogger()
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(console)
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
    Creates a directory contining one or more arch specific yum repositories by using local
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
    We've see the koji client occasionally get
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
              help='clean=remove all builds on start and successful exit; leave=leave builds attached which the invocation attempted to sign')
@click.option('--poll-for', default=15, type=click.INT, help='Allow up to this number of minutes for auto-signing')
@click.option('--event', required=False, default=None, help='The brew event for the desired tag states')
@click.option('--include-embargoed', default=False, is_flag=True,
              help='If specified, embargoed/unshipped RPMs will be included in the plashet')
def from_tags(config, brew_tag, embargoed_brew_tag, embargoed_nvr, signing_advisory_id, signing_advisory_mode, poll_for, event, include_embargoed):
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

    koji_proxy = KojiWrapper(koji.ClientSession(config.brew_url, opts={'krbservice': 'brewhub', 'serverca': '/etc/pki/brew/legacy.crt'}))
    koji_proxy.gssapi_login()
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
            embargoed_tag_nvrs.add(build['nvr'])
    logger.info('Will treat the following nvrs as potentially embargoed: {}'.format(embargoed_tag_nvrs))

    actual_embargoed_nvrs = list()  # A list of nvrs detected as embargoed
    desired_nvrs = set()
    nvr_product_version = {}
    for tag, product_version in brew_tag:

        released_package_nvrs = {}  # maps released package names to the most recently released package (parsed) nvr
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
                released_package_nvrs[package_name] = parse_nvr(build['nvr'])

        for build in koji_proxy.listTagged(tag, latest=True, inherit=False, event=event, type='rpm'):
            package_name = build['package_name']
            nvr = build['nvr']
            parsed_nvr = parse_nvr(nvr)

            released_nvr = None  # if the package has shipped before, the parsed nvr of the most recently shipped
            if package_name in released_package_nvrs:
                released_nvr = released_package_nvrs[package_name]

            if package_name in config.exclude_package:
                logger.info(f'Skipping tagged but command line excluded package: {nvr}')
                continue

            if config.include_package and package_name not in config.include_package:
                logger.info(f'Skipping tagged but not command line included package: {nvr}')
                continue

            if '.p1' in nvr or nvr in embargoed_tag_nvrs:
                # p1 or inclusion in the embargoed_tag_nvrs indicates this rpm is embargoed OR *was* embargoed.
                # We can ignore it if it has already shipped.
                if released_nvr is None or compare_nvr(parsed_nvr, released_nvr) > 0:  # Is our nvr > last shipped?
                    # Our embargoed build has not been shipped.
                    actual_embargoed_nvrs.append(nvr)  # Record that at the time of build, this was considered embargoed

                    if not include_embargoed:
                        # We are being asked to build a plashet without embargoed RPMs. We need to find a stand-in.
                        # Search through the tag's package history to find the last build that was NOT embargoed.
                        unembargoed_nvr = None
                        for build in koji_proxy.listTagged(tag, package=package_name, inherit=True, event=event, type='rpm'):
                            test_nvr = build['nvr']
                            parsed_test_nvr = parse_nvr(test_nvr)
                            if released_nvr is None or compare_nvr(parsed_test_nvr, released_nvr) > 0:  # If this nvr hasn't shipped
                                if '.p1' in test_nvr or test_nvr in embargoed_tag_nvrs:  # Looks like this one is embargoed too
                                    continue
                            unembargoed_nvr = test_nvr
                            break

                        if unembargoed_nvr is None:
                            raise IOError(f'Unable to build unembargoed plashet. Lastest build of {package_name} ({nvr}) is embargoed but unable to find unembargoed version in history')
                        plashet_concerns.append(f'Swapping embargoed nvr {nvr} for unembargoed nvr {unembargoed_nvr}.')
                        logger.info(plashet_concerns[-1])
                        nvr = unembargoed_nvr
                else:
                    logger.info(f'NVR {nvr} was potentially embargoed, but has already shipped')

            if released_nvr:
                if compare_nvr(parsed_nvr, released_nvr) < 0:  # if the current nvr is less than the released NVR
                    msg = f'Skipping tagged {nvr} because it is older than a released version: {released_nvr}'
                    plashet_concerns.append(msg)
                    logger.error(msg)
                    continue

            logger.info(f'{tag} contains package: {nvr}')
            desired_nvrs.add(nvr)
            nvr_product_version[nvr] = product_version

    if config.include_package and len(config.include_package) != len(desired_nvrs):
        raise IOError(f'Did not find all command line included packages {config.include_package}; only found {desired_nvrs}')

    if signing_advisory_id and signing_advisory_mode == 'clean':
        # Remove all builds attached to advisory before attempting signing
        update_advisory_builds(config, errata_proxy, signing_advisory_id, [], nvr_product_version)

    # Did any of the archs require signed content?
    possible_signing_needed = signed_desired(config)

    if possible_signing_needed:
        logger.info(f'At least one architecture requires signed nvrs')

        if signing_advisory_id:
            nvrs_for_advisory = []

            for nvr in desired_nvrs:
                if not is_signed(config, nvr):
                    logger.info(f'Found an unsigned nvr (will attempt to signed): {nvr}')
                    nvrs_for_advisory.append(nvr)

            logger.info(f'Updating advisory to get nvrs signed: {signing_advisory_id}')
            update_advisory_builds(config, errata_proxy, signing_advisory_id, nvrs_for_advisory, nvr_product_version)

        else:
            logger.warning('No signing advisory specified; will simply poll and hope')

        # Whether we've attached to advisory or no, wait until signing require is met
        # or throw exception on timeout.
        logger.info('Waiting for all nvrs to be signed..')
        for nvr in desired_nvrs:
            poll_for -= assert_signed(config, nvr)

    if signing_advisory_id and signing_advisory_mode == 'clean':
        # Seems that everything is signed; remove builds from the advisory.
        update_advisory_builds(config, errata_proxy, signing_advisory_id, [], nvr_product_version)

    extra_embargo_info = {  # Data related to embargos that will be written into the plashet.yml
        'embargoed_permitted': include_embargoed,  # Whether we included or excluded these nvrs in the plashet
        'detected_as_embargoed': actual_embargoed_nvrs,
    }

    extra_data = {  # Data that will be included in the plashet.yml after assembly.
        'embargo_info': extra_embargo_info
    }

    assemble_repo(config, desired_nvrs, event_info, extra_data=extra_data)


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

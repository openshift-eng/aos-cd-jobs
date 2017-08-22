from __future__ import print_function
import yum
import sys
import os.path
import argparse
import logging
import rpmUtils.miscutils as rpmutils

# Remove duplicate packages from different repositories
def remove_duplicate_pkgs(available_pkgs):
	available_pkgs_tups = []
	uniq_available_pkgs = []
	for pkg in available_pkgs:
		if pkg.pkgtup not in available_pkgs_tups:
			available_pkgs_tups.append(pkg.pkgtup)
			uniq_available_pkgs.append(pkg)
	return uniq_available_pkgs

# Get all the matching `MAJOR.MINOR` versions of provided input package nerva
# Returned list of package versions is in `'pkg_version'-'pkg_release'` format ,eg: `1.3.0-3.el7`
def get_matching_versions(input_pkg_name, available_pkgs, search_version):
	release_pkgs = []
	pre_release_pkgs = []
	for pkg in available_pkgs:
		if pkg.version.startswith(search_version):
			if pkg.release.startswith("0"):
				pre_release_pkgs.append("-".join([pkg.version, pkg.release]))
			else:
				release_pkgs.append("-".join([pkg.version, pkg.release]))
	# If there are any release versions use those, otherwise use pre-release versions
	if release_pkgs:
		return release_pkgs
	elif pre_release_pkgs:
		return pre_release_pkgs
	else:
		print("[ERROR] Can not determine install and upgrade version for the `" + input_pkg_name + "` package", file=sys.stderr)
		sys.exit(1)

# Get only last version from version list
def get_last_version(version_list):
	return version_list[-1]

# Return minor version of provided package version-release pair
def get_minor_version(pkg_version_release):
	return pkg_version_release.split('.', 2)[1]

# Print install, upgrade and upgrade_release versions of desired package to STDOUT.
# The upgrade version will be printed only in case there is more then one version of packages previous minor release.
def print_version_vars(install_version, upgrade_version):
	used_pkg_name = pkg_name.upper().replace("-", "_")
	print (used_pkg_name + "_INSTALL_VERSION=" + install_version)
	print (used_pkg_name + "_INSTALL_MINOR_VERSION=" + get_minor_version(install_version))
	print (used_pkg_name + "_UPGRADE_RELEASE_VERSION=" + upgrade_version)
	print (used_pkg_name + "_UPGRADE_RELEASE_MINOR_VERSION=" + get_minor_version(upgrade_version))

def determine_search_versions(pkg_name, pkg_version):
	parsed_version = pkg_version.split('.')
	major = parsed_version[0]
	minor = parsed_version[1]
	search_install_version = schema_change_check(pkg_name, major, str(int(minor) - 1))
	search_upgrade_version = schema_change_check(pkg_name, major, minor)
	return search_install_version, search_upgrade_version

# Cause of the origin version schema change we had to manually change the version just for this
# case where we should look for 1.5.x versions if the built version is origin-3.6.x
def schema_change_check(pkg_name, search_major_version, search_minor_version):
	if pkg_name == "origin" and search_major_version == "3" and int(search_minor_version) <= 5:
		search_major_version = "1"
	search_version = ".".join([search_major_version, search_minor_version])
	return search_version

def sort_pkgs(available_pkgs):
	# There is an issue that origin-3.6.0-0.0.alpha.0.1 package was wrongly tagged and proper tag
	# should be origin-3.6.0-0.alpha.0.1. Because of this issue we have to ignore the package for
	# installation and upgrade considerations.
	exceptional_pkg = {}
	for pkg in available_pkgs:
		if (pkg.name == "origin" and pkg.version == "3.6.0" and pkg.release == "0.0.alpha.0.1") or \
		   (pkg.name == "atomic-openshift-utils" and pkg.version == "3.6.173.0.7" and pkg.release == "1.git.0.f6f19ed.el7"):
			available_pkgs.remove(pkg)
			break

	available_pkgs.sort(lambda x, y: rpmutils.compareEVR((x.epoch, x.version, x.release), (y.epoch, y.version, y.release)))
	return available_pkgs


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("input_pkg", type=str, help="Package NEVRA")
	parser.add_argument("--dependency_branch", type=str, default='master', help="Dependency target branch")
	args = parser.parse_args()

	pkg_name, pkg_version, pkg_release, pkg_epoch, pkg_arch = rpmutils.splitFilename(args.input_pkg)

	# If dependency target branch is specified for a release or an enterprise release use that version so proper install
	# and upgrade version are set. The major version of the searched version is taken from the package version from the
	# input and the minor version is from the debendency branch version.
	#
	# example: OPENSHFIT_ANSIBLE INPUT PKG VERSION  - openshift-ansible-3.6.142-1.git.0.90b5f60.el7
	#          OPENSHIFT_ANSIBLE_TARGET_BRANCH      - release-1.5
	#
	#          OPENSHIFT_ANSIBLE_INSTALL_VERSION=3.4.115-1.git.0.94b720b.el7
	#          OPENSHIFT_ANSIBLE_INSTALL_MINOR_VERSION=4
	#          OPENSHIFT_ANSIBLE_UPGRADE_RELEASE_VERSION=3.5.96-1.git.0.88536f9.el7
	#          OPENSHIFT_ANSIBLE_UPGRADE_RELEASE_MINOR_VERSION=5
	#
	if args.dependency_branch.startswith("release") or args.dependency_branch.startswith("enterprise"):
		pkg_major_version = pkg_version.split(".")[0]
		dependency_minor_version = args.dependency_branch.split("-")[1].split(".")[1]
		pkg_version = ".".join([pkg_major_version, dependency_minor_version])
	else:
		major, minor, rest = pkg_version.split('.', 2)
		pkg_version = '.'.join([major, minor])

	if any(char.isalpha() for char in pkg_version):
		print ("[ERROR] Incorrect package nevra format: " + args.input_pkg, file=sys.stderr)
		sys.exit(2)

	yb = yum.YumBase()
	# Turn the yum logger onto critical messages only so we approximate --quiet
	# flag in the CLI and get no garbage output like `Loaded plugins: amazon-id, rhui-lb`
	logging.getLogger("yum.verbose.YumPlugins").setLevel(logging.CRITICAL)

	generic_holder = yb.doPackageLists('all', patterns=[pkg_name], showdups=True)
	available_pkgs = rpmutils.unique(generic_holder.available + generic_holder.installed)
	available_pkgs = remove_duplicate_pkgs(available_pkgs)
	available_pkgs = sort_pkgs(available_pkgs)

	search_install_version, search_upgrade_version = determine_search_versions(pkg_name, pkg_version)
	matching_install_pkgs = get_matching_versions(pkg_name, available_pkgs, search_install_version)
	matching_upgrade_pkgs = get_matching_versions(pkg_name, available_pkgs, search_upgrade_version)

	install_version = get_last_version(matching_install_pkgs)
	upgrade_version = get_last_version(matching_upgrade_pkgs)

	print_version_vars(install_version, upgrade_version)
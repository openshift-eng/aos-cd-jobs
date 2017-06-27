import yum
import sys
import os.path
import argparse
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
		print("[ERROR] Can not determine install and upgrade version for the `" + input_pkg_name + "` package", sys.stderr)
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

def determine_install_version(pkg_name, pkg_version):
	parsed_version = pkg_version.split('.')
	major = parsed_version[0]
	minor = parsed_version[1]
	# Cause of the origin version schema change we had to manually change the version just for this 
	# case where we should look for 1.5.x versions if the built version is origin-3.6.x 
	if pkg_name == "origin" and major == "3" and minor == "6":
		major = "1"
	search_version = '.'.join([major, str(int(minor) - 1)])
	return search_version

def sort_pkgs(available_pkgs):
	# There is an issue that origin-3.6.0-0.0.alpha.0.1 package was wrongly tagged and proper tag
	# should be origin-3.6.0-0.alpha.0.1. Because of this issue we have to ignore the package for
	# installation and upgrade considerations.
	exceptional_pkg = {}
	for pkg in available_pkgs:
		if (pkg.name == "origin" and pkg.version == "3.6.0" and pkg.release == "0.0.alpha.0.1"):
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
	# and upgrade version are set.
	#
	# example: OPENSHIFT_ANSIBLE_TARGET_BRANCH - release-1.5
	#          ORIGIN_TARGET_BRANCH            - master
	#
	#          ORIGIN_INSTALL_VERSION=1.4.1-1.el7
	#          ORIGIN_INSTALL_MINOR_VERSION=4
	#          ORIGIN_UPGRADE_RELEASE_VERSION=1.5.1-1.el7
	#          ORIGIN_UPGRADE_RELEASE_MINOR_VERSION=5
	#
	if args.dependency_branch.startswith("release") or args.dependency_branch.startswith("enterprise"):
		pkg_version = args.dependency_branch.split("-")[1]
	else:
		major, minor, rest = pkg_version.split('.', 2)
		pkg_version = '.'.join([major, minor])

	if any(char.isalpha() for char in pkg_version):
		print ("[ERROR] Incorrect package nevra format: " + args.input_pkg, sys.stderr)
		sys.exit(2)

	yb = yum.YumBase()
	# Have to redirect redirect the yum configuration to /dev/null cause we dont want to have any additional output
	# that configuration prints. eg: `Loaded plugins: amazon-id, rhui-lb`  
	old_stdout = sys.stdout
	sys.stdout = open(os.devnull, 'w')
	# Need make sure that all the packages are listed, cause if excluders are enabled for some reason,
	# listing of origin or docker pkgs will be disabled, based on the enabled excluder.
	yb.conf.disable_excludes = ["all"]
	sys.stdout = old_stdout

	generic_holder = yb.doPackageLists('all', patterns=[pkg_name], showdups=True)
	available_pkgs = rpmutils.unique(generic_holder.available + generic_holder.installed)

	available_pkgs = remove_duplicate_pkgs(available_pkgs)
	available_pkgs = sort_pkgs(available_pkgs)

	search_install_version = determine_install_version(pkg_name, pkg_version)

	matching_install_pkgs = get_matching_versions(pkg_name, available_pkgs, search_install_version)
	matching_upgrade_pkgs = get_matching_versions(pkg_name, available_pkgs, pkg_version)
	install_version = get_last_version(matching_install_pkgs)
	upgrade_version = get_last_version(matching_upgrade_pkgs)

	print_version_vars(install_version, upgrade_version)
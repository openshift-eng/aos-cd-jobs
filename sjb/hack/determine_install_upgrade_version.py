import yum
import sys
import os.path
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

# Get only install(first) and upgrade(last) versions from version list
def get_install_upgrade_version(version_list):
	if len(version_list) > 1: 
		return [version_list[0],version_list[len(version_list)-1]]
	return [version_list[0]]

# Return minor version of provided package version-release pair
def get_minor_version(pkg_version_release):
	return pkg_version_release.split('.', 2)[1]

# Return version of provided package version-release pair
def get_version(pkg_version_release):
	return pkg_version_release.split('-', 2)[0]

# Print install, upgrade and upgrade_release versions of desired package to STDOUT.
# The upgrade version will be printed only in case there is more then one version of packages previous minor release. 
def print_version_vars(version_list):
	used_pkg_name = pkg_name.upper().replace("-", "_")
	print (used_pkg_name + "_INSTALL_VERSION=" + version_list[0])
	print (used_pkg_name + "_INSTALL_MINOR_VERSION=" + get_minor_version(version_list[0]))
	if len(version_list) > 1:
		print (used_pkg_name + "_UPGRADE_VERSION=" + version_list[1])
		print (used_pkg_name + "_UPGRADE_MINOR_VERSION=" + get_minor_version(version_list[1]))
		print (used_pkg_name + "_UPGRADE_VERSION_PKG_VERSION=" + get_version(version_list[1]))
	print (used_pkg_name + "_UPGRADE_RELEASE_VERSION=" + pkg_version + "-" + pkg_release)
	print (used_pkg_name + "_UPGRADE_RELEASE_MINOR_VERSION=" + get_minor_version(pkg_version + "-" + pkg_release))

def determine_search_version(pkg_name, pkg_version):
	major, minor, rest = pkg_version.split('.', 2)
	# Cause of the origin version schema change we had to manually change the version just for this 
	# case where we should look for 1.5.x versions if the built version is origin-3.6.x 
	if pkg_name == "origin" and major == "3" and minor == "6":
		major = "1"
	search_version = '.'.join([major, str(int(minor) - 1)])
	return search_version

if __name__ == "__main__":
	if len(sys.argv) != 2:
	    print ("[ERROR] No NEVRA provided!", sys.stderr)
	    sys.exit(3)
	input_pkg = sys.argv[1]
	pkg_name, pkg_version, pkg_release, pkg_epoch, pkg_arch = rpmutils.splitFilename(input_pkg)

	if any(char.isalpha() for char in pkg_version):
		print ("[ERROR] Incorrect package nevra format: " + input_pkg, sys.stderr)
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
	available_pkgs = rpmutils.unique(yb.doPackageLists('available', patterns=[pkg_name], showdups=True).available)
	search_version = determine_search_version(pkg_name, pkg_version)
	available_pkgs = remove_duplicate_pkgs(available_pkgs)
	available_pkgs.sort(lambda x, y: rpmutils.compareEVR((x.epoch, x.version, x.release), (y.epoch, y.version, y.release)))
	matching_pkgs = get_matching_versions(pkg_name, available_pkgs, search_version)
	install_upgrade_version_list = get_install_upgrade_version(matching_pkgs)
	print_version_vars(install_upgrade_version_list)
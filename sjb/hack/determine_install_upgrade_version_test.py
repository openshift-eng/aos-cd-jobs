import unittest
import rpmUtils.miscutils as rpmutils
from determine_install_upgrade_version import *

class TestPackage(object):
	def __init__(self, version, release, vra, pkgtup):
		self.version = version
		self.release = release
		self.vra = vra
		self.pkgtup = pkgtup

	@classmethod
	def create_test_packages(self, test_pkgs):
		test_pkgs_objs = []
		for pkg in test_pkgs:
			pkg_name, pkg_version, pkg_release, pkg_epoch, pkg_arch =  rpmutils.splitFilename(pkg)
			pkg_vra = pkg_version + "-" + pkg_release + "." + pkg_arch
			pkg_tup = (pkg_name , pkg_arch, pkg_epoch, pkg_version, pkg_release)
			test_pkgs_objs.append(TestPackage(pkg_version, pkg_release, pkg_vra, pkg_tup))
		return test_pkgs_objs

class RemoveDuplicatePackages(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_removing_single_duplicate_package(self):
		""" when is multiple duplicate packages, return only one """
		test_pkgs = ["origin-1.4.1-1.el7.x86_64", "origin-1.5.0-0.4.el7.x86_64", "origin-1.5.0-0.4.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		result_pkgs_objs = test_pkgs_objs[:2]
		self.assertEqual(remove_duplicate_pkgs(test_pkgs_objs), result_pkgs_objs)

	def test_removing_no_duplicate_package(self):
		""" when there is no duplicate package, return the single one """
		test_pkgs = ["origin-1.4.1-1.el7.x86_64", "origin-1.5.0-0.4.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		result_pkgs_objs = test_pkgs_objs[:2]
		self.assertEqual(remove_duplicate_pkgs(test_pkgs_objs), result_pkgs_objs)

class GetMatchingVersionTestCase(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_get_matching_versions(self):
		""" when only one matching version exist and its pre-release, it is returned """
		test_pkgs = ["origin-1.4.1-1.el7.x86_64", "origin-1.5.0-0.4.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		self.assertEqual(get_matching_versions('origin', test_pkgs_objs, '1.5'), ['1.5.0-0.4.el7'])

	def test_with_single_pre_release(self):
		""" when only one pre-release version exist, it is returned """
		test_pkgs = ["origin-1.5.0-0.4.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		self.assertEqual(get_matching_versions('origin', test_pkgs_objs, '1.5'), ['1.5.0-0.4.el7'])

	def test_with_multiple_pre_release(self):
		""" when only one pre-release version exist, it is returned """
		test_pkgs = ["origin-1.5.0-0.4.el7.x86_64", "origin-1.5.2-0.1.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		self.assertEqual(get_matching_versions('origin', test_pkgs_objs, '1.5'), ['1.5.0-0.4.el7', '1.5.2-0.1.el7'])

	def test_with_single_release(self):
		""" when both release and pre-release versions exist, only release versions are returned """
		test_pkgs = ["origin-1.5.0-0.4.el7.x86_64", "origin-1.5.0-1.1.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		self.assertEqual(get_matching_versions('origin', test_pkgs_objs, '1.5'), ["1.5.0-1.1.el7"])

	def test_with_muptiple_release(self):
		""" when both release and pre-release versions exist, only release version is returned """
		test_pkgs = ["origin-1.5.0-0.4.el7.x86_64", "origin-1.5.0-1.1.el7.x86_64", "origin-1.5.2-1.1.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		self.assertEqual(get_matching_versions('origin', test_pkgs_objs, '1.5'), ["1.5.0-1.1.el7", "1.5.2-1.1.el7"])

	def test_with_no_matches(self):
		test_pkgs = ["origin-1.2.0-0.4.el7.x86_64", "origin-1.3.0-1.1.el7.x86_64", "origin-1.4.2-1.1.el7.x86_64"]
		test_pkgs_objs = TestPackage.create_test_packages(test_pkgs)
		self.assertRaises(SystemExit, get_matching_versions, 'origin', test_pkgs_objs, '1.5')

class DetermineSearchVersionTestCase(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_origin_with_standard_versioning_schema(self):
		""" when the origin version is higher then the first version of the new origin versioning schema - origin-3.6 """
		self.assertEqual(determine_search_version("origin", "3.7.0"), "3.6")

	def test_origin_with_standard_to_legacy_versioning_schema(self):
		""" when the origin version is the first from the new origin versioning schema - origin-3.6 """
		self.assertEqual(determine_search_version("origin", "3.6.0"), "1.5")

	def test_origin_with_legacy_schema(self):
		""" when the origin version is in the old versioning schema """
		self.assertEqual(determine_search_version("origin", "1.5.0"), "1.4")

	def test_openshift_ansible_with_standard_versioning_schema(self):
		""" when openshift-ansible, which doesnt have different versioning schema, is in 3.7 version  """
		self.assertEqual(determine_search_version("openshift-ansible", "3.7.0"), "3.6")

	def test_openshift_ansible_with_standard_to_legacy_versioning_schema(self):
		""" when openshift-ansible, which doesnt have different versioning schema is in 3.6 version """
		self.assertEqual(determine_search_version("openshift-ansible", "3.6.0"), "3.5")

	def test_openshift_ansible_with_legacy_versioning_schema(self):
		""" when openshift-ansible, which doesnt have different versioning schema is in 3.4 version """
		self.assertEqual(determine_search_version("openshift-ansible", "3.5.0"), "3.4")

class GetInstallUpgradeVersionTestCase(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_with_multiple_matching_release_versions(self):
		""" when multiple matching version are present in released versions """
		matching_versions = ["1.2.0-1.el7", "1.2.2-1.el7", "1.2.5-1.el7"]
		install_upgrade_versions = ["1.2.0-1.el7", "1.2.5-1.el7"]
		self.assertEqual(get_install_upgrade_version(matching_versions), install_upgrade_versions)

	def test_with_single_matching_release_version(self):
		""" when only a single matching version is present in released versions """
		matching_versions = ["1.5.0-1.4.el7"]
		install_upgrade_versions = ["1.5.0-1.4.el7"]
		self.assertEqual(get_install_upgrade_version(matching_versions), install_upgrade_versions)

	def test_with_multiple_matching_pre_release_versions(self):
		""" when multiple matching pre-release version are present in pre-released versions """
		matching_versions = ["1.2.0-0.el7", "1.2.2-0.el7", "1.2.5-0.el7"]
		install_upgrade_versions = ["1.2.0-0.el7", "1.2.5-0.el7"]
		self.assertEqual(get_install_upgrade_version(matching_versions), install_upgrade_versions)

	def test_with_single_matching_pre_release_version(self):
		""" when only single matching pre-release version is present in pre-released versions """
		matching_versions = ["1.5.0-0.4.el7"]
		install_upgrade_versions = ["1.5.0-0.4.el7"]
		self.assertEqual(get_install_upgrade_version(matching_versions), install_upgrade_versions)

class GetVersionTestCase(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_get_version(self):
		""" when package version is picked its version-release pair """
		version_release = "1.5.0-0.4.el7"
		self.assertEqual(get_version(version_release), "1.5.0")

	def test_get_minor_version(self):
		""" when package minor version is picked its version-release pair """
		version_release = "1.5.0-0.4.el7"
		self.assertEqual(get_minor_version(version_release), "5")

if __name__ == '__main__':
	unittest.main()
import unittest
from determine_install_upgrade_version import *

class TestPackage(object):
	def __init__(self, name, version, release, epoch, vra, pkgtup):
		self.name = name
		self.version = version
		self.release = release
		self.epoch = epoch
		self.vra = vra
		self.pkgtup = pkgtup

	def __eq__(self, other):
		return self.__dict__ == other.__dict__

	@classmethod
	def create_test_packages(self, test_pkgs):
		test_pkgs_objs = []
		for pkg in test_pkgs:
			pkg_name, pkg_version, pkg_release, pkg_epoch, pkg_arch =  rpmutils.splitFilename(pkg)
			pkg_vra = pkg_version + "-" + pkg_release + "." + pkg_arch
			pkg_tup = (pkg_name , pkg_arch, pkg_epoch, pkg_version, pkg_release)
			test_pkgs_objs.append(TestPackage(pkg_name, pkg_version, pkg_release, pkg_epoch, pkg_vra, pkg_tup))
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
		self.assertEqual(determine_search_versions("origin", "3.7.0"), ("3.6", "3.7"))

	def test_origin_with_short_standard_versioning_schema(self):
		""" when the origin version is in short format and higher then the first version of the new origin versioning schema - origin-3.6 """
		self.assertEqual(determine_search_versions("origin", "3.7"), ("3.6", "3.7"))

	def test_origin_with_standard_to_legacy_versioning_schema(self):
		""" when the origin version is the first from the new origin versioning schema - origin-3.6 """
		self.assertEqual(determine_search_versions("origin", "3.6.0"), ("1.5", "3.6"))

	def test_origin_with_short_standard_to_legacy_versioning_schema(self):
		""" when the origin version is in short format and first from the new origin versioning schema - origin-3.6 """
		self.assertEqual(determine_search_versions("origin", "3.6"), ("1.5", "3.6"))

	def test_origin_with_legacy_schema(self):
		""" when the origin version is in the old versioning schema """
		self.assertEqual(determine_search_versions("origin", "1.5.0"), ("1.4", "1.5"))

	def test_origin_with_short_legacy_schema(self):
		""" when the origin version is in short and old versioning schema """
		self.assertEqual(determine_search_versions("origin", "1.5"), ("1.4", "1.5"))

	def test_openshift_ansible_with_standard_versioning_schema(self):
		""" when openshift-ansible, which doesnt have different versioning schema, is in 3.7 version  """
		self.assertEqual(determine_search_versions("openshift-ansible", "3.7.0"), ("3.6", "3.7"))

	def test_openshift_ansible_with_standard_to_legacy_versioning_schema(self):
		""" when openshift-ansible, which doesnt have different versioning schema is in 3.6 version """
		self.assertEqual(determine_search_versions("openshift-ansible", "3.6.0"), ("3.5", "3.6"))

	def test_openshift_ansible_with_short_standard_to_legacy_versioning_schema(self):
		""" when openshift-ansible, which doesnt have different versioning schema, is in short format and in 3.6 version """
		self.assertEqual(determine_search_versions("openshift-ansible", "3.6"), ("3.5", "3.6"))

	def test_openshift_ansible_with_legacy_versioning_schema(self):
		""" when openshift-ansible, which doesnt have different versioning schema is in 3.4 version """
		self.assertEqual(determine_search_versions("openshift-ansible", "3.5.0"), ("3.4", "3.5"))

class SchemaChangeCheckTestCase(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_origin_package_with_new_schema(self):
		""" when origin package is in 3.6 version """
		self.assertEqual(schema_change_check("origin", "3", "6"), "3.6")

	def test_origin_package_with_old_schema(self):
		""" when origin package is in 1.5 version """
		self.assertEqual(schema_change_check("origin", "3", "5"), "1.5")

	def test_non_origin_package_with_new_schema(self):
		""" when origin package is in 3.6 version """
		self.assertEqual(schema_change_check("openshift-ansible", "3", "6"), "3.6")

	def test_non_origin_package_with_old_schema(self):
		""" when origin package is in 3.5 version """
		self.assertEqual(schema_change_check("openshift-ansible", "3", "5"), "3.5")

class GetLastVersionTestCase(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_with_multiple_matching_release_versions(self):
		""" when multiple matching version are present in released versions """
		matching_versions = ["1.2.0-1.el7", "1.2.2-1.el7", "1.2.5-1.el7"]
		install_version = "1.2.5-1.el7"
		self.assertEqual(get_last_version(matching_versions), install_version)

	def test_with_single_matching_release_version(self):
		""" when only a single matching version is present in released versions """
		matching_versions = ["1.5.0-1.4.el7"]
		install_version = "1.5.0-1.4.el7"
		self.assertEqual(get_last_version(matching_versions), install_version)

	def test_with_multiple_matching_pre_release_versions(self):
		""" when multiple matching pre-release version are present in pre-released versions """
		matching_versions = ["1.2.0-0.el7", "1.2.2-0.el7", "1.2.5-0.el7"]
		install_version = "1.2.5-0.el7"
		self.assertEqual(get_last_version(matching_versions), install_version)

	def test_with_single_matching_pre_release_version(self):
		""" when only single matching pre-release version is present in pre-released versions """
		matching_versions = ["1.5.0-0.4.el7"]
		install_version = "1.5.0-0.4.el7"
		self.assertEqual(get_last_version(matching_versions), install_version)

class SortPackagesTestCase(unittest.TestCase):
	"Test for `determine_install_upgrade_version.py`"

	def test_sort_packages_with_exceptional_origin_pkg(self):
		""" when sorting origin packages with exceptional origin-3.6.0-0.0.alpha.0.1 package """
		test_pkgs = ["origin-3.6.0-0.0.alpha.0.1.el7", "origin-3.6.0-0.alpha.0.2.el7"]
		properly_sorted_pkgs = ["origin-3.6.0-0.alpha.0.2.el7"]
		test_pkgs_obj = TestPackage.create_test_packages(test_pkgs)
		properly_sorted_pkgs_obj = TestPackage.create_test_packages(properly_sorted_pkgs)
		sorted_test_pkgs_obj = sort_pkgs(test_pkgs_obj)
		self.assertEqual(sorted_test_pkgs_obj, properly_sorted_pkgs_obj)

	def test_sort_packages_with_same_minor_version(self):
		""" when sorting origin packages within the same minor version """
		test_pkgs = ["origin-1.5.1-1.el7", "origin-1.5.0-1.el7"]
		properly_sorted_pkgs = ["origin-1.5.0-1.el7", "origin-1.5.1-1.el7"]
		test_pkgs_obj = TestPackage.create_test_packages(test_pkgs)
		properly_sorted_pkgs_obj = TestPackage.create_test_packages(properly_sorted_pkgs)
		sorted_test_pkgs_obj = sort_pkgs(test_pkgs_obj)
		self.assertEqual(sorted_test_pkgs_obj, properly_sorted_pkgs_obj)

	def test_sort_packages_with_different_minor_version(self):
		""" when sorting origin packages with different minor version """
		test_pkgs = ["origin-1.5.1-1.el7", "origin-1.4.0-1.el7"]
		properly_sorted_pkgs = ["origin-1.4.0-1.el7", "origin-1.5.1-1.el7"]
		test_pkgs_obj = TestPackage.create_test_packages(test_pkgs)
		properly_sorted_pkgs_obj = TestPackage.create_test_packages(properly_sorted_pkgs)
		sorted_test_pkgs_obj = sort_pkgs(test_pkgs_obj)
		self.assertEqual(sorted_test_pkgs_obj, properly_sorted_pkgs_obj)


if __name__ == '__main__':
	unittest.main()
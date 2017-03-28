import unittest
import sys

import sanity_check
import git

class ValidateTests(unittest.TestCase):
    """ Tests for commit validation """

    ####################################
    # Test for validate_commit_message #
    ####################################

    def test_validate_commit_message(self):
        """
        Test commit message validation
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick pan4tha [SQUASH][BRANDING] OAuth server branding",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick d5f4ssw [DROP] webconsole bump",
        ]
        from StringIO import StringIO
        out = StringIO()

        for commit in commits:
            real_commit = git.create_commit(commit)
            sanity_check.validate_commit_message(real_commit)

        commits = [
        "pick c21ea24 [CARRY] OAuth server branding",
        "pick pan4tha [SQUASH] OAuth server branding",
        "pick ba426b9 [CARRY][] empty type",
        "pick d5f4ssw webconsole bump",
        "pick ba426b9 [OTHER][CARRY] thought I knew what I was doing",
        ]
        for commit in commits:
            real_commit = git.create_commit(commit)
            self.assertRaises(SystemExit, sanity_check.validate_commit_message, real_commit, out)

    ###########
    # Helpers #
    ###########

    def assertFailure(self, func, commits, expected):
        from StringIO import StringIO

        real_commits = convert_commits(commits)
        out = StringIO()

        self.assertRaises(SystemExit, func, real_commits, out)
        self.assertEquals(out.getvalue().strip(), expected)

    def assertSuccess(self, func, commits):
        real_commits = convert_commits(commits)

        try:
            func(real_commits)
        except:
            print "Unexpected error:", sys.exc_info()[0]
            raise

    ###################################
    # Tests for validate_tito_commits #
    ###################################

    def test_missing_tito_tag(self):
        """
        Latest tito commit is missing.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick c21ea21 [SQUASH][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        ]
        expected = "No commit from `tito tag` found!"
        self.assertFailure(sanity_check.validate_tito_commits, commits, expected)

    def test_missing_generated_tito_diff(self):
        """
        Generated tito diff is missing.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick c21ea21 [SQUASH][BRANDING] OAuth server branding",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        ]
        expected = "No carry commit for `.spec` file found!"
        self.assertFailure(sanity_check.validate_tito_commits, commits, expected)

    def test_tito_tag_before_generated_tito_diff(self):
        """
        Latest tito commit is before the commit that contains all the
        generated tito diff.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick c21ea21 [SQUASH][BRANDING] OAuth server branding",
        "pick c21ea22 [SQUASH][DIFFERENT] Different kind of stuff",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        ]
        expected = "Found the `tito tag` commit before the `.spec` file  commit!"
        self.assertFailure(sanity_check.validate_tito_commits, commits, expected)

    def test_valid_tito_commits(self):
        """
        Tito commits are valid.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        ]
        self.assertSuccess(sanity_check.validate_tito_commits, commits)

    ##############################
    # Tests for validate_carries #
    ##############################

    def test_squash_no_matching_carry(self):
        """
        [SQUASH] commit has a type that is not matching any [CARRY].
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick c21ea21 [SQUASH][BRANDING] OAuth server branding",
        "pick c21ea22 [SQUASH][DIFFERENT] Different kind of stuff",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        ]
        expected = "Not all SQUASH commits correspond to a CARRY commit!"
        self.assertFailure(sanity_check.validate_carries, commits, expected)

    def test_squash_no_carry(self):
        """
        [SQUASH] commit has a type that is not matching any [CARRY].
        """

        commits = [
        "pick c21ea21 [SQUASH][BRANDING] OAuth server branding",
        "pick c21ea22 [SQUASH][DIFFERENT] Different kind of stuff",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        ]
        expected = "Not all SQUASH commits correspond to a CARRY commit!"
        self.assertFailure(sanity_check.validate_carries, commits, expected)

    def test_duplicate_carries(self):
        """
        Duplicate [CARRY] commits exist.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick c21ea21 [SQUASH][BRANDING] OAuth server branding",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        ]
        expected = "Found more than one carry commit with the same type!"
        self.assertFailure(sanity_check.validate_carries, commits, expected)

    def test_squashes_and_drops(self):
        """
        Rebase where additional SQUASH and DROP commits have been added
        since the last rebase.
        """

        commits = [
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick 22a76cd [DROP] bump origin-web-console 0c5b53c",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 4365d5d [DROP][INVESTIGATE] Weird shell diffs",
        "pick 8ff2968 [DROP][FIXME] Change image build and drop this cluster up flag",
        "pick 5hfos3s [SQUASH][BUILD] Check in new shiny script for OSE",
        "pick c21ea22 [SQUASH][BRANDING] Additional OAuth server branding",
        ]
        self.assertSuccess(sanity_check.validate_carries, commits)


def convert_commits(commits):
    real_commits = []
    for line in commits:
        real_commits.append(git.create_commit(line))
    return real_commits


if __name__ == '__main__':
    unittest.main()


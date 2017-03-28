import unittest

import rebase
import git

class RemoveDropCommitsTests(unittest.TestCase):
    """ Tests for rebasing """

    def assertEquality(self, func, commits, expected):
        real_commits = convert_commits(commits)
        real_expected = convert_commits(expected)

        real_commits = func(real_commits)
        self.assertEqual(len(real_commits), len(real_expected))
        for index, commit in enumerate(real_commits):
            self.assertEqual(commit.action, real_expected[index].action)
            self.assertEqual(commit.hash, real_expected[index].hash)
            self.assertEqual(commit.subject, real_expected[index].subject)

    #################################
    # Tests for remove_drop_commits #
    #################################

    def test_simple_drop(self):
        """
        Drop all commits with a [DROP] prefix.
        """

        commits = [
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick 22a76cd [DROP] bump origin-web-console 0c5b53c",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 4365d5d [DROP][INVESTIGATE] Weird shell diffs",
        "pick 8ff2968 [DROP][FIXME] Change image build and drop this cluster up flag",
        ]
        expected = [
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        ]
        self.assertEquality(rebase.remove_drop_commits, commits, expected)


    def test_noop_drop(self):
        """
        No-op if no [DROP] commits exist.
        """

        commits = [
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 22a76cd [SQUASH][BRANDING] New branding code",
        ]
        expected = [
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 22a76cd [SQUASH][BRANDING] New branding code",
        ]
        self.assertEquality(rebase.remove_drop_commits, commits, expected)


    #################################
    # Tests for squash_tito_commits #
    #################################

    def test_squash_tito_commit(self):
        """
        Squash tito commit to generated tito diff commit.
        """

        commits = [
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 22a76cd [SQUASH][BRANDING] New branding code",
        ]
        expected = [
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "fixup ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 22a76cd [SQUASH][BRANDING] New branding code",
        ]
        self.assertEquality(rebase.squash_tito_commits, commits, expected)

    def test_squash_tito_commit_reorder(self):
        """
        Squash tito commit to generated tito diff commit.
        The tito commit will be reordered.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        ]
        expected = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "fixup ba426b9 Automatic commit of package [atomic-openshift] release [3.5.0.50-1].",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        ]
        self.assertEquality(rebase.squash_tito_commits, commits, expected)


    ##################################
    # Tests for squash_named_commits #
    ##################################

    def test_squash_named_commits_noop(self):
        """
        No-op if there are no commits to squash.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        ]
        expected = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        ]
        self.assertEquality(rebase.squash_named_commits, commits, expected)    

    def test_squash_named_commits(self):
        """
        Simple commit squash.
        """

        commits = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        "pick 59dn2sf [SQUASH][BUILD] Changes to tito",
        ]
        expected = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "fixup 59dn2sf [SQUASH][BUILD] Changes to tito",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        ]
        self.assertEquality(rebase.squash_named_commits, commits, expected)  

    def test_squash_named_commits_edge(self):
        """
        Squash commit checked in before its corresponding carry.
        """

        commits = [
        "pick 59dn2sf [SQUASH][BUILD] Changes to tito",
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        ]
        expected = [
        "pick c21ea24 [CARRY][BRANDING] OAuth server branding",
        "pick 59dn2sf [CARRY][BUILD] Tooling diff for OSE",
        "fixup 59dn2sf [SQUASH][BUILD] Changes to tito",
        "pick 975a829 [CARRY][BUILD_GEN] Specfile updates",
        ]
        self.assertEquality(rebase.squash_named_commits, commits, expected)


    ############################
    # Tests commit_types_match #
    ############################

    def test_commit_types_match(self):
        """
        Test prefixes for carry commits
        """

        tests = [
        ["[BRANDING] OAuth server branding", "[BRANDING] More branding"],
        ["[BUILD] Specfile updates", "[BUILD] More building code"],
        ]
        for tc in tests:
            self.assertEqual(rebase.commit_types_match(*tc), True)

        tests = [
        ["[BRANDING] OAuth server branding", "[BUILD] More branding"],
        ["Specfile updates", "[BUILD] Specfile updates"],
        ]
        for tc in tests:
            self.assertEqual(rebase.commit_types_match(*tc), False)


def convert_commits(commits):
    real_commits = []
    for line in commits:
        if line.startswith(git.Action.pick):
            real_commits.append(git.create_commit(line))
        elif line.startswith(git.Action.fixup):
            real_commits.append(git.create_commit(line))

    return real_commits


if __name__ == '__main__':
    unittest.main()

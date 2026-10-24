"""Check the copied job's input contract and shell argument handling."""

import re
import subprocess
from pathlib import Path
from unittest import TestCase, main


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "jobs/build/layered-products-prepare-release/Jenkinsfile"
UNIFIED = ROOT / "jobs/build/layered-products-prepare-release-unified/Jenkinsfile"


class TestPrepareReleaseUnifiedJob(TestCase):
    def setUp(self):
        self.original = ORIGINAL.read_text()
        self.job = UNIFIED.read_text()

    def test_branch_updater_discovers_both_jobs(self):
        from types import SimpleNamespace
        from aos_cd_jobs.updater import list_jobs

        jobs = list_jobs(SimpleNamespace(working_dir=str(ROOT)))
        self.assertIn('build/layered-products-prepare-release', jobs)
        self.assertIn('build/layered-products-prepare-release-unified', jobs)

    def test_copy_retains_credentials_and_original_parameters(self):
        credentials = r"credentialsId: '([^']+)', variable: '([^']+)'"
        self.assertEqual(re.findall(credentials, self.original), re.findall(credentials, self.job))
        original_params = set(re.findall(r"name: '([A-Z_]+)'", self.original))
        copied_params = re.findall(r"name: '([A-Z_]+)'", self.job)
        self.assertEqual(len(copied_params), len(set(copied_params)))
        self.assertEqual(set(copied_params), original_params | {"CREATE_UNIFIED_FBCS", "UNIFIED_FBC_GROUPS"})
        self.assertRegex(self.job, r"(?s)name: 'CREATE_UNIFIED_FBCS'.*?defaultValue: false")
        self.assertNotIn("CREATE_UNIFIED_FBCS", self.original)

    def test_command_branches_forward_only_their_mode_inputs(self):
        unified, ordinary = re.search(
            r'(?s)if \(params.CREATE_UNIFIED_FBCS\) \{\s*(cmd \+= .*?)\} else \{\s*(cmd \+= .*?)\}',
            self.job,
        ).groups()
        self.assertIn('"--create-unified-fbcs"', unified)
        self.assertIn('"--unified-fbc-groups", unifiedGroups', unified)
        self.assertNotIn('"--group"', unified)
        self.assertNotIn('"--assembly"', unified)
        self.assertIn('"--group", params.GROUP.trim()', ordinary)
        self.assertIn('"--assembly", params.ASSEMBLY.trim()', ordinary)
        self.assertNotIn('"--unified-fbc-groups"', ordinary)
        self.assertIn('params.GROUP?.trim() || params.ASSEMBLY?.trim() || params.REFRESH_FBCS', self.job)

    def test_shell_quoting_preserves_literal_arguments(self):
        replacement = re.search(r'''it.toString\(\).replace\("'", "([^"]+)"\)''', self.job).group(1)
        replacement = replacement.replace('\\\\', '\\')
        args = ['--unified-fbc-groups', 'quay-3.18,quay-3.17', "don't expand $(printf unsafe)", 'two words']
        quoted = ' '.join("'" + arg.replace("'", replacement) + "'" for arg in args)
        result = subprocess.run(['bash', '-c', "printf '%s\\0' " + quoted], check=True, capture_output=True)
        self.assertEqual(result.stdout.decode().split('\0')[:-1], args)


if __name__ == '__main__':
    main()

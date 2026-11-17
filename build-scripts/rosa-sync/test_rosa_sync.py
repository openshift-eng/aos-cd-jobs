"""Local shell integration tests; every AWS command is replaced by a fake executable.

Run with: python3 -m unittest discover -s build-scripts/rosa-sync -p 'test_*.py'
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('jq'), 'jq is required by rosa_sync.sh')
class RosaSyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = self.root / 'calls.jsonl'
        self.meta = self.root / 'meta.json'
        self.meta.write_text(json.dumps({'amis': [{'name': 'us-east-1', 'hvm': 'ami-12345678'}]}))
        fake = self.root / 'aws'
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['AWS_TEST_CALLS'], 'a') as stream:
    stream.write(json.dumps(args) + '\\n')
scenario = os.environ.get('AWS_TEST_SCENARIO', '')
if args[:2] == ['sts', 'get-caller-identity']:
    if scenario == 'identity_failure':
        sys.exit(1)
    print('111122223333')
elif 'describe-images' in args:
    if '--image-ids' in args:
        if scenario == 'source_failure':
            sys.exit(1)
        print('None' if scenario == 'source_missing' else 'rhcos-source')
    else:
        print('ami-87654321' if scenario == 'existing' else 'None')
elif args[:2] == ['ec2', 'copy-image']:
    if '--dry-run' not in args:
        print('fake live copy')
    elif scenario == 'unexpected_success':
        print('unexpected success')
    else:
        code = {'denied': 'UnauthorizedOperation', 'auth_failure': 'AuthFailure'}.get(scenario, 'DryRunOperation')
        if os.environ.get('AWS_CLI_ERROR_FORMAT') == 'json':
            print(json.dumps({'Code': code}), file=sys.stderr)
        else:
            print('An error occurred (' + code + ') when calling the CopyImage operation: ' + os.environ['AWS_SECRET_ACCESS_KEY'], file=sys.stderr)
        sys.exit(255)
else:
    sys.exit('Unexpected AWS command')
''')
        fake.chmod(0o755)
        self.env = {
            **os.environ,
            'PATH': str(self.root) + os.pathsep + os.environ['PATH'],
            'AWS_TEST_CALLS': str(self.calls),
            'AWS_ACCESS_KEY_ID': 'test-access-value',
            'AWS_SECRET_ACCESS_KEY': 'test-secret-value',
            # A user-configured error format must not break the permission check.
            'AWS_CLI_ERROR_FORMAT': 'json',
        }

    def run_sync(self, dry_run='true', scenario='', trace=False):
        self.env['AWS_TEST_SCENARIO'] = scenario
        args = ['bash'] + (['-x'] if trace else []) + [str(Path(__file__).with_name('rosa_sync.sh')), str(self.meta)]
        if dry_run is not None:
            args.append(dry_run)
        result = subprocess.run(args, env=self.env, text=True, capture_output=True, timeout=10)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        self.assertNotIn(self.env['AWS_ACCESS_KEY_ID'], result.stdout + result.stderr)
        self.assertNotIn(self.env['AWS_SECRET_ACCESS_KEY'], result.stdout + result.stderr)
        return result, calls

    def test_dry_run_accepts_permission_response(self):
        result, calls = self.run_sync(trace=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Authenticated AWS account', result.stdout)
        self.assertIn('EC2 image reads verified', result.stdout)
        self.assertIn('CopyImage permission verified', result.stdout)
        self.assertEqual(len(calls), 4)
        self.assertIn('--dry-run', calls[-1])

    def test_existing_ami_still_checks_copy_permission(self):
        result, calls = self.run_sync(scenario='existing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('a live run would skip', result.stdout)
        self.assertIn('--dry-run', calls[-1])

    def test_denied_and_invalid_credentials_fail(self):
        for scenario, code in [('denied', 'UnauthorizedOperation'), ('auth_failure', 'AuthFailure')]:
            with self.subTest(scenario=scenario):
                result, calls = self.run_sync(scenario=scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(code, result.stderr)
                self.assertNotIn('CopyImage permission verified', result.stdout)
                self.assertIn('--dry-run', calls[-1])

    def test_unexpected_zero_exit_is_not_permission_verification(self):
        result, _ = self.run_sync(scenario='unexpected_success')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no permission-check result', result.stderr)

    def test_failed_identity_stops_before_ec2(self):
        result, calls = self.run_sync(scenario='identity_failure')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:2], ['sts', 'get-caller-identity'])

    def test_source_read_failure_does_not_attempt_copy(self):
        for scenario in ['source_failure', 'source_missing']:
            with self.subTest(scenario=scenario):
                result, calls = self.run_sync(scenario=scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any('copy-image' in call for call in calls))

    def test_missing_ami_does_not_call_aws(self):
        self.meta.write_text('{"amis": []}')
        result, calls = self.run_sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_invalid_dry_run_flag_fails_closed(self):
        result, calls = self.run_sync(dry_run='tru')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_live_existing_ami_still_skips_copy(self):
        result, calls = self.run_sync(dry_run='false', scenario='existing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 2)
        self.assertFalse(any('copy-image' in call or 'get-caller-identity' in call for call in calls))

    def test_live_missing_ami_copies_without_dry_run_flag(self):
        for dry_run in ['false', None]:
            with self.subTest(dry_run=dry_run):
                result, calls = self.run_sync(dry_run=dry_run)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(calls[-1][:2], ['ec2', 'copy-image'])
                self.assertNotIn('--dry-run', calls[-1])


if __name__ == '__main__':
    unittest.main()

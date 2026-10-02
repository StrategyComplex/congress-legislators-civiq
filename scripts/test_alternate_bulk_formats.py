"""Offline CLI contracts using copied scripts and synthetic YAML only."""

import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    """No production input, output, network, or mocked conversion is involved."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'checkout'
        scripts = self.source / 'scripts'
        scripts.mkdir(parents=True)
        self.script = scripts / 'alternate_bulk_formats.py'
        shutil.copyfile(Path(__file__).with_name('alternate_bulk_formats.py'), self.script)
        shutil.copyfile(Path(__file__).with_name('converter_safety.py'), scripts / 'converter_safety.py')
        self.expected = {
            'legislators-current': [{'id': {'bioguide': 'SYNTHETIC1'},
                                     'name': {'first': 'Example', 'last': 'Official'},
                                     'terms': [{'type': 'rep', 'start': '2030-01-03', 'state': 'CA'}]}],
            'legislators-district-offices': [{'id': {'bioguide': 'SYNTHETIC1'},
                                              'offices': [{'id': 'example', 'city': 'Example City'}]}],
            'legislators-social-media': [{'id': {'bioguide': 'SYNTHETIC1'},
                                          'social': {'twitter_id': '9007199254740993'}}],
            'committees-current': [{'thomas_id': 'HSEX', 'type': 'house', 'name': 'Example Committee'}],
            'committee-membership-current': {'HSEX': [{'bioguide': 'SYNTHETIC1', 'rank': 1}]},
        }
        for name, data in self.expected.items():
            (self.source / (name + '.yaml')).write_text(json.dumps(data), encoding='utf-8')
        # Real YAML exercises safe date conversion and lossless large integer IDs.
        (self.source / 'legislators-current.yaml').write_text(
            '- id: {bioguide: SYNTHETIC1}\n'
            '  name: {first: Example, last: Official}\n'
            '  terms:\n    - type: rep\n      start: 2030-01-03\n      state: CA\n',
            encoding='utf-8')
        (self.source / 'legislators-social-media.yaml').write_text(
            '- id: {bioguide: SYNTHETIC1}\n  social: {twitter_id: 9007199254740993}\n',
            encoding='utf-8')
        (self.source / 'legislators-current.yaml.pickle').write_bytes(b'not a pickle')
        self.output = self.root / 'fresh' / 'json'
        self.cwd = self.root / 'unrelated-cwd'
        self.cwd.mkdir()

    def run_cli(self, *args):
        env = os.environ.copy()
        env.pop('PYTHONDONTWRITEBYTECODE', None)
        env.pop('PYTHONPATH', None)
        return subprocess.run([sys.executable, str(self.script), *map(str, args)],
                              cwd=self.cwd, env=env, text=True, capture_output=True, timeout=30)

    def snapshot(self):
        return {str(p.relative_to(self.source)): None if p.is_dir() else
                (p.read_bytes(), p.stat().st_mtime_ns) for p in self.source.rglob('*')}

    def test_json_only_preserves_all_five_contracts_without_csv_or_source_writes(self):
        before = self.snapshot()
        result = self.run_cli('--input-dir', self.source, '--output-dir', self.output,
                              '--json-only', '--force-refresh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p.name for p in self.output.iterdir()},
                         {name + '.json' for name in self.expected})
        for name, expected in self.expected.items():
            self.assertEqual(json.loads((self.output / (name + '.json')).read_bytes()), expected)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.cwd.iterdir()), [])
        self.assertEqual(list(self.root.rglob('*.csv')), [])

    def test_explicit_destination_skips_existing_unless_forced(self):
        args = ('--input-dir', self.source, '--output-dir', self.output, '--json-only')
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        destination = self.output / 'legislators-current.json'
        first = destination.read_bytes()
        result = self.run_cli(*args, '--force-refresh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(destination.read_bytes(), first)
        source = self.source / 'legislators-current.yaml'
        timestamp = source.stat().st_mtime_ns
        source.write_text(source.read_text().replace('Example', 'Changed'), encoding='utf-8')
        os.utime(source, ns=(timestamp, timestamp))
        before = self.snapshot()
        output_time = destination.stat().st_mtime_ns
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((destination.read_bytes(), destination.stat().st_mtime_ns),
                         (first, output_time))
        result = self.run_cli(*args, '--force-refresh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(destination.read_bytes())[0]['name']['first'], 'Changed')
        self.assertEqual(self.snapshot(), before)

    def test_legacy_defaults_generate_json_and_csv_and_refresh_from_any_cwd(self):
        (self.source / 'legislators-historical.yaml').write_text('[]\n', encoding='utf-8')
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        destination = self.source / 'alternate_formats/json/legislators-current.json'
        self.assertEqual(json.loads(destination.read_bytes()), self.expected['legislators-current'])
        csv_dir = self.source / 'alternate_formats/csv'
        self.assertEqual({p.name for p in csv_dir.iterdir()}, {
            'legislators-current.csv', 'legislators-historical.csv',
            'legislators-district-offices.csv', 'committee-membership-current.csv'})
        with (csv_dir / 'legislators-current.csv').open(encoding='utf-8', newline='') as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(rows[0]['bioguide_id'], 'SYNTHETIC1')
        self.assertEqual(rows[0]['twitter_id'], '9007199254740993')
        destination.write_text('[]', encoding='utf-8')
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(destination.read_bytes()), self.expected['legislators-current'])
        self.assertEqual(list(self.cwd.iterdir()), [])

    def test_invalid_build_options_fail_before_writing(self):
        before = self.snapshot()
        for args in [('--output-dir', self.output),
                     ('--json-only', '--output-dir', self.source / 'generated'),
                     ('--json-only', '--output-dir', self.output, '--input-dir', self.root / 'missing')]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.output.exists())
                self.assertEqual(self.snapshot(), before)

    def test_yaml_python_tags_are_rejected_without_output_or_source_changes(self):
        # Sorted first, so rejection also precedes any partial output.
        (self.source / 'committee-membership-current.yaml').write_text(
            '!!python/tuple [1, 2]\n', encoding='utf-8')
        before = self.snapshot()
        result = self.run_cli('--json-only', '--output-dir', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('could not determine a constructor', result.stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_keys_merges_and_recursive_aliases_fail_closed(self):
        # Membership sorts first; nested committee/ID keys exercise the same loader.
        source = self.source / 'committee-membership-current.yaml'
        cases = [
            ('HSEX: []\nHSEX: []\n', 'duplicate YAML mapping key'),
            ('HSEX: [{id: one, id: two}]\n', 'duplicate YAML mapping key'),
            ('HSEX: [{roles: [], roles: []}]\n', 'duplicate YAML mapping key'),
            ('HSEX: [{committee: {name: One, name: Two}}]\n', 'duplicate YAML mapping key'),
            ('HSEX: [{true: a, 1: b}]\n', 'duplicate YAML mapping key'),
            ('HSEX: [{<<: {rank: 1}, rank: 2}]\n', 'merge directives'),
            ('HSEX: [{<<: {rank: 1}, <<: {name: One}}]\n', 'merge directives'),
            ('HSEX: &loop [*loop]\n', 'recursive YAML aliases'),
        ]
        for text, message in cases:
            with self.subTest(text=text):
                source.write_text(text, encoding='utf-8')
                before = self.snapshot()
                result = self.run_cli('--json-only', '--output-dir', self.output, '--force-refresh')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.output.exists())
                self.assertEqual(self.snapshot(), before)

    def test_benign_aliases_preserve_memberships(self):
        (self.source / 'committee-membership-current.yaml').write_text(
            'HSEX: &members [{bioguide: SYNTHETIC1, rank: 1}]\nSSEX: *members\n', encoding='utf-8')
        before = self.snapshot()
        result = self.run_cli('--json-only', '--output-dir', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.output / 'committee-membership-current.json').read_bytes())
        self.assertEqual(data, {'HSEX': [{'bioguide': 'SYNTHETIC1', 'rank': 1}],
                                'SSEX': [{'bioguide': 'SYNTHETIC1', 'rank': 1}]})
        self.assertEqual(self.snapshot(), before)

    def test_symlink_destinations_fail_before_any_write_even_when_skipping(self):
        for kind in ('file', 'dangling', 'root', 'ancestor'):
            for force in (False, True):
                with self.subTest(kind=kind, force=force):
                    base = self.root / (kind + str(force))
                    base.mkdir()
                    output = base / 'output'
                    target = base / 'target'
                    target.mkdir()
                    sentinel = target / 'sentinel'
                    sentinel.write_bytes(b'untouched')
                    target_before = (sentinel.read_bytes(), sentinel.stat().st_mtime_ns,
                                     target.stat().st_mtime_ns)
                    missing = target / 'missing'
                    if kind == 'root':
                        output.symlink_to(target, target_is_directory=True)
                    elif kind == 'ancestor':
                        link = base / 'link'
                        link.symlink_to(target, target_is_directory=True)
                        output = link / 'new-output'
                    else:
                        output.mkdir()
                        (output / 'legislators-current.json').symlink_to(
                            missing if kind == 'dangling' else self.source / 'legislators-current.yaml')
                    before = self.snapshot()
                    result = self.run_cli('--json-only', '--output-dir', output,
                                          *(['--force-refresh'] if force else []))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('Symlink output path', result.stderr)
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual((sentinel.read_bytes(), sentinel.stat().st_mtime_ns,
                                      target.stat().st_mtime_ns), target_before)
                    self.assertEqual(list(target.iterdir()), [sentinel])
                    if kind in ('file', 'dangling'):
                        self.assertEqual([p.name for p in output.iterdir()], ['legislators-current.json'])

    def test_nested_committee_duplicate_never_replaces_existing_artifact(self):
        (self.source / 'committees-current.yaml').write_text(
            '- thomas_id: HSEX\n  subcommittees: [{name: One, name: Two}]\n', encoding='utf-8')
        self.output.mkdir(parents=True)
        destination = self.output / 'committees-current.json'
        destination.write_bytes(b'previous artifact')
        old = (destination.read_bytes(), destination.stat().st_mtime_ns)
        before = self.snapshot()
        result = self.run_cli('--json-only', '--output-dir', self.output, '--force-refresh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate YAML mapping key', result.stderr)
        self.assertEqual((destination.read_bytes(), destination.stat().st_mtime_ns), old)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_csv_link_is_rejected_before_json_or_csv_writes(self):
        (self.source / 'legislators-historical.yaml').write_text('[]\n', encoding='utf-8')
        csv_dir = self.source / 'alternate_formats/csv'
        csv_dir.mkdir(parents=True)
        (csv_dir / 'legislators-current.csv').symlink_to(self.source / 'legislators-current.yaml')
        before = self.snapshot()
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Symlink output path', result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.source / 'alternate_formats/json').exists())

    def test_force_replaces_hardlinked_output_without_truncating_source(self):
        self.output.mkdir(parents=True)
        destination = self.output / 'legislators-current.json'
        os.link(self.source / 'legislators-current.yaml', destination)
        before = self.snapshot()
        result = self.run_cli('--json-only', '--output-dir', self.output, '--force-refresh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(destination.read_bytes()), self.expected['legislators-current'])
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()

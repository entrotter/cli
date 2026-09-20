"""Negative CI-policy tests; scanner/dependency data here are labeled fixtures."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


def load(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dependencies = load('check_dependency_manifest')
security = load('check_security')


class QualityPolicyTests(unittest.TestCase):
    def test_local_sdk_cannot_hide_version_or_dependency_changes(self):
        project = {'project': {'dependencies': ['entrotter-sdk==0.1.0']},
                   'build-system': {'requires': ['setuptools==84.0.0']}}
        sdk = {'project': {'name': 'entrotter-sdk', 'version': '0.1.0', 'dependencies': []},
               'build-system': {'requires': ['setuptools==84.0.0']}}
        lock = 'setuptools==84.0.0 \\\n --hash=sha256:fixture\n'
        self.assertEqual(dependencies.check(project, lock, sdk)['local_runtime'],
                         {'entrotter-sdk': '0.1.0'})
        for field, value in [('name', 'unrelated'), ('version', '0.2.0'),
                             ('dependencies', ['unreviewed==1']),
                             ('optional-dependencies', {'extra': ['unreviewed==1']})]:
            changed = deepcopy(sdk)
            changed['project'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                dependencies.check(project, lock, changed)
        sdk['build-system']['requires'] = ['unreviewed==1']
        with self.assertRaises(ValueError):
            dependencies.check(project, lock, sdk)

    def test_dependency_declarations_cannot_escape_audited_lock(self):
        project = {'project': {'dependencies': []},
                   'build-system': {'requires': ['setuptools==84.0.0']}}
        lock = 'setuptools==84.0.0 \\\n --hash=sha256:fixture\n'
        self.assertEqual(dependencies.check(project, lock)['audited_locked_packages'], 1)
        for requirement in ['new==1', 'setuptools>=84', 'setuptools==83.0.0']:
            changed = deepcopy(project)
            changed['project']['dependencies'] = [requirement]
            with self.subTest(requirement=requirement), self.assertRaises(ValueError):
                dependencies.check(changed, lock)
        project['project']['optional-dependencies'] = {'feature': ['new==1']}
        with self.assertRaises(ValueError):
            dependencies.check(project, lock)

    def test_no_empty_partial_skipped_or_unreviewed_security_success(self):
        report = {'errors': [], 'results': [], 'metrics': {
            '_totals': {'loc': 1, 'skipped_tests': 0}, 'src/sample.py': {'loc': 1}}}
        security.check(report, {'src/sample.py'})
        for changed in [
            {**report, 'errors': ['unreadable source']},
            {**report, 'results': [{'test_id': 'example finding'}]},
            {**report, 'metrics': {'_totals': {'loc': 1}}},
            {**report, 'metrics': {'_totals': {'loc': 0}}},
            {**report, 'metrics': {'_totals': {'loc': 1, 'skipped_tests': 1}}},
        ]:
            with self.subTest(report=changed), self.assertRaises(ValueError):
                security.check(changed, {'src/sample.py'})


if __name__ == '__main__':
    unittest.main()

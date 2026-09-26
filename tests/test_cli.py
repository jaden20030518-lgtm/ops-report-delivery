import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_demo_is_runnable_offline_and_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            for _ in range(2):
                result = subprocess.run([sys.executable, '-m', 'report_delivery', 'demo', '--out', directory],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data['status'], 'demo_completed')
                self.assertEqual(data['rows'], 3)
                self.assertFalse(data['network_accessed'])
            manifest = json.loads((Path(directory)/'run/manifest.json').read_text())
            self.assertTrue(manifest['demo'])
            self.assertFalse(manifest['ready_for_upload'])

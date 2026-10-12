"""Black-box checks for random selection, remembered history and explicit requests."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('stickers.py')


class StickerChecks(unittest.TestCase):
    def invoke(self, *arguments):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPT),
                               *arguments, '--json'], capture_output=True, text=True,
                              encoding='utf-8')

    def test_separate_invocations_do_not_repeat_adjacent_stickers(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'recent.json'
            ids = []
            for _ in range(30):
                result = self.invoke('auto', '完成', '--state-file', str(state))
                self.assertEqual(result.returncode, 0, result.stderr)
                item = json.loads(result.stdout)
                self.assertTrue(Path(item['path']).is_file())
                self.assertIn(item['id'], ['done', 'ta-da', 'happy'])
                ids.append(item['id'])
            self.assertTrue(all(a != b for a, b in zip(ids, ids[1:])))
            self.assertEqual(len(set(ids)), 3)
            self.assertEqual(json.loads(state.read_text(encoding='utf-8'))['recent'][0], ids[-1])

    def test_visible_previous_sticker_wins_when_small_pool_exhausted(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'recent.json'
            state.write_text(json.dumps({'recent': ['welcome', 'hello', 'okay']}))
            result = self.invoke('auto', '招呼', '--avoid', '29,11', '--state-file', str(state))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['id'], 'welcome')

    def test_explicit_requests_are_stable_and_do_not_create_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'recent.json'
            for query in ('07', 'done', '完成'):
                result = self.invoke('pick', query, '--state-file', str(state))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['id'], 'done')
            self.assertFalse(state.exists())

    def test_bad_input_preserves_history_and_corrupt_history_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'recent.json'
            state.write_text('broken')
            for arguments in [('auto', '不存在'), ('auto', '完成', '--avoid', '不存在')]:
                result = self.invoke(*arguments, '--state-file', str(state))
                self.assertEqual(result.returncode, 2)
                self.assertFalse(result.stdout)
                self.assertEqual(state.read_text(), 'broken')
            result = self.invoke('auto', '收到', '--avoid', '22', '--state-file', str(state))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(json.loads(result.stdout)['id'], 'okay')
            self.assertEqual(set(json.loads(state.read_text(encoding='utf-8'))), {'recent'})


if __name__ == '__main__':
    unittest.main()

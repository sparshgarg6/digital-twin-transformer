"""CLI integration checks using invented connector responses only."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'convert_messages_export.py'
CHAT = 'synthetic-chat'
OUTPUT_NAMES = ('messages.jsonl', 'transcript.txt', 'export-summary.json')


def fixture_pages() -> list[dict]:
    def message(day, sender, body, **extra):
        return {'chat': 'chat1', 'date': f'2025-01-{day:02d}T12:00:00Z',
                'sender': sender, 'body': body, **extra}

    def sender(ref, label):
        return {'local_ref': ref, 'name': f'Participant {label}',
                'handle': f'participant-{label.lower()}@example.invalid', 'service': 'iMessage'}

    # Local sender references deliberately resolve differently on each page.
    return [
        {'chats': [{'local_ref': 'chat1', 'chat_guid': CHAT, 'display_name': 'Synthetic chat'}],
         'senders': [sender('sender1', 'A'), sender('sender2', 'B')],
         'messages': [message(7, 'me', 'Invented café 🌱\nA second line.', is_unread=False),
                      message(6, 'sender1', 'Invented reply.'),
                      message(5, 'unknown', None),
                      message(4, 'sender2', 'Invented repeated text.')],
         'next_cursor': 'synthetic-next-page'},
        {'chats': [{'local_ref': 'chat1', 'chat_guid': CHAT, 'display_name': 'Synthetic chat'}],
         'senders': [sender('sender1', 'B'), sender('sender2', 'A')],
         'messages': [message(4, 'sender1', 'Invented repeated text.'),
                      message(3, 'me', None, attachments=[{'id': 'synthetic-attachment',
                                                          'name': 'invented-image.png'}]),
                      message(2, 'sender2', '')],
         'next_cursor': None},
    ]


class ExportConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'pages'
        self.source.mkdir()
        self.output = self.root / 'export'
        self.pages = fixture_pages()

    def write_pages(self, *, text_envelope=False):
        for index, page in enumerate(self.pages, 1):
            if text_envelope:
                payload = {'content': [{'type': 'text', 'text': json.dumps(page)}]}
            elif index == 2:
                payload = {'structuredContent': page, 'content': []}
            else:
                payload = page
            (self.source / f'{index:04d}.json').write_text(
                json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    def convert(self, *extra, text_envelope=False):
        self.write_pages(text_envelope=text_envelope)
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--source-dir', str(self.source),
             '--output-dir', str(self.output), '--chat-guid', CHAT,
             '--expected-total', '7', '--expected-sent', '2', '--expected-received', '5',
             '--upper-bound', '2025-02-01T00:00:00Z', *extra],
            capture_output=True, text=True, check=False)

    def assert_failed(self, result, fragment):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(fragment, result.stderr)
        self.assertFalse(any((self.output / name).exists() for name in OUTPUT_NAMES))

    def test_preserves_records_and_page_local_references(self):
        result = self.convert('--owner-name', 'Owner', '--timezone', 'UTC')
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(line) for line in
                   (self.output / 'messages.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(records), 7)
        self.assertEqual([record['source_traversal_ordinal'] for record in records],
                         [6, 5, 4, 3, 2, 1, 0])
        self.assertEqual([record['sender'] for record in records],
                         ['Participant A', 'Owner', 'Participant B', 'Participant B',
                          'Unknown', 'Participant A', 'Owner'])
        self.assertEqual(records[2]['body'], records[3]['body'])
        self.assertEqual(records[2]['timestamp_utc'], records[3]['timestamp_utc'])
        self.assertNotEqual(records[2]['source_page'], records[3]['source_page'])
        self.assertEqual(records[0]['body'], '')
        self.assertIsNone(records[1]['body'])
        self.assertEqual(records[1]['attachments'][0]['id'], 'synthetic-attachment')
        self.assertIsNone(records[4]['is_from_me'])
        self.assertFalse(records[0]['is_from_me'])
        self.assertTrue(records[-1]['is_from_me'])
        self.assertFalse(records[-1]['is_unread'])
        self.assertEqual(records[-1]['body'], 'Invented café 🌱\nA second line.')
        transcript = (self.output / 'transcript.txt').read_text(encoding='utf-8')
        self.assertIn('Invented café 🌱\nA second line.', transcript)
        self.assertIn('Attachment metadata only:', transcript)
        summary = json.loads((self.output / 'export-summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['counts'], {'total': 7, 'sent': 2, 'received': 5,
                         'unknown_sender': 1, 'attachment_items': 1,
                         'messages_with_attachments': 1, 'missing_body': 2, 'empty_body': 1})
        self.assertEqual(summary['resolved_received'], 4)
        self.assertIn('non-me', summary['received_count_definition'])
        self.assertFalse(summary['deduplication_performed'])
        self.assertFalse(summary['attachments_downloaded'])
        self.assertTrue(summary['pagination_complete'])
        self.assertEqual([page['messages'] for page in summary['source_pages']], [4, 3])
        self.assertTrue(all(len(page['sha256']) == 64 for page in summary['source_pages']))
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for name in OUTPUT_NAMES:
            self.assertEqual(stat.S_IMODE((self.output / name).stat().st_mode), 0o600)

    def test_default_owner_and_text_envelope_preserve_existing_directory_mode(self):
        self.output.mkdir(mode=0o755)
        self.output.chmod(0o755)
        result = self.convert(text_envelope=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(line) for line in
                   (self.output / 'messages.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(records[-1]['sender'], 'Me')
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o755)

    def test_rejects_foreign_chat(self):
        self.pages[1]['chats'][0]['chat_guid'] = 'another-synthetic-chat'
        self.assert_failed(self.convert(), 'unexpected chat')

    def test_rejects_out_of_order_pages(self):
        self.pages[1]['messages'][0]['date'] = '2025-01-08T12:00:00Z'
        self.assert_failed(self.convert(), 'timestamp order')

    def test_rejects_count_mismatch(self):
        self.assert_failed(self.convert('--expected-received', '4'), 'Count mismatch for received')

    def test_rejects_exclusive_upper_bound(self):
        self.assert_failed(self.convert('--upper-bound', '2025-01-07T12:00:00Z'),
                           'exclusive upper bound')

    def test_rejects_incomplete_pagination(self):
        for page_index, cursor in ((0, None), (1, 'synthetic-next-page')):
            with self.subTest(page=page_index):
                self.pages = fixture_pages()
                self.pages[page_index]['next_cursor'] = cursor
                self.assert_failed(self.convert(), 'continuation cursor')

    def test_rejects_repeated_cursors(self):
        third = copy.deepcopy(self.pages[1])
        third['messages'] = []
        self.pages[1]['next_cursor'] = self.pages[0]['next_cursor']
        self.pages.append(third)
        self.assert_failed(self.convert(), 'repeated continuation cursor')

    def test_refuses_to_overwrite_any_output_filename(self):
        self.output.mkdir()
        for name in OUTPUT_NAMES:
            with self.subTest(filename=name):
                target = self.output / name
                target.write_text('Existing invented content.', encoding='utf-8')
                result = self.convert()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('refusing overwrite', result.stderr)
                self.assertEqual(target.read_text(encoding='utf-8'), 'Existing invented content.')
                self.assertEqual(list(self.output.iterdir()), [target])
                target.unlink()


if __name__ == '__main__':
    unittest.main()

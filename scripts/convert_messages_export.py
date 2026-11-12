#!/usr/bin/env python3
"""Validate paginated Messages connector data and write a local text export.

Reads only the explicitly supplied directory of JSON response pages. It does not
open Messages databases, connect to services, or download attachments.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

PAGE_NAME = re.compile(r'^(\d{4,})\.json$')


class ExportError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ExportError(message)


def timestamp(value: object, location: str) -> datetime:
    require(isinstance(value, str), f'{location}: date must be a string')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ExportError(f'{location}: invalid ISO-8601 date') from None
    require(parsed.tzinfo is not None, f'{location}: date must have a timezone')
    return parsed.astimezone(timezone.utc)


def utc_iso(value: datetime) -> str:
    return value.isoformat().replace('+00:00', 'Z')


def load_page(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise ExportError(f'{path.name}: unable to read a JSON response') from None
    # Accept bare structured payloads or standard MCP CallToolResult envelopes.
    if isinstance(obj, dict) and 'structuredContent' in obj:
        require(not obj.get('isError'), f'{path.name}: tool response is an error')
        obj = obj['structuredContent']
    elif isinstance(obj, dict) and 'content' in obj and 'messages' not in obj:
        require(not obj.get('isError'), f'{path.name}: tool response is an error')
        require(isinstance(obj['content'], list), f'{path.name}: invalid response content')
        texts = [x.get('text') for x in obj['content']
                 if isinstance(x, dict) and x.get('type') == 'text']
        require(len(texts) == 1, f'{path.name}: ambiguous text response envelope')
        try:
            obj = json.loads(texts[0])
        except (TypeError, ValueError):
            raise ExportError(f'{path.name}: text response is not a JSON page') from None
    require(isinstance(obj, dict), f'{path.name}: page must be an object')
    for key in ('messages', 'chats', 'senders'):
        require(isinstance(obj.get(key), list), f'{path.name}: missing {key} array')
    return obj


def ref_map(rows: list, label: str) -> dict:
    result = {}
    for row in rows:
        require(isinstance(row, dict), f'{label}: entry must be an object')
        ref = row.get('local_ref')
        require(isinstance(ref, str) and bool(ref), f'{label}: invalid local_ref')
        require(ref not in result, f'{label}: duplicate local_ref')
        result[ref] = row
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--chat-guid', required=True)
    parser.add_argument('--expected-total', required=True, type=int)
    parser.add_argument('--expected-sent', required=True, type=int)
    parser.add_argument('--expected-received', required=True, type=int,
                        help='All non-me records, including literal unknown senders')
    parser.add_argument('--upper-bound', required=True,
                        help='Exclusive timezone-qualified ISO-8601 bound used for all pages')
    parser.add_argument('--owner-name', default='Me', help='Display name for me records (default: Me)')
    parser.add_argument('--timezone', default='UTC', help='Transcript timezone (default: UTC)')
    args = parser.parse_args()
    try:
        local_tz = ZoneInfo(args.timezone)
    except (KeyError, ValueError):
        raise ExportError('Unknown transcript timezone') from None
    source = args.source_dir.resolve(strict=True)
    output = args.output_dir.absolute()
    require(source.is_dir(), 'Source must be a directory')
    require(not output.is_symlink(), 'Output directory must not be a symlink')
    require(not output.exists() or output.is_dir(), 'Output path must be a directory')
    output_names = ('messages.jsonl', 'transcript.txt', 'export-summary.json')
    require(not any(os.path.lexists(output / name) for name in output_names),
            'An output file already exists; refusing overwrite')
    require(all(x >= 0 for x in (args.expected_total, args.expected_sent, args.expected_received)),
            'Expected counts must be nonnegative')
    require(args.expected_sent + args.expected_received <= args.expected_total,
            'Expected sent and received counts exceed total')
    upper = timestamp(args.upper_bound, 'upper bound')
    pages = sorted((int(match.group(1)), path) for path in source.iterdir()
                   if path.is_file() and (match := PAGE_NAME.fullmatch(path.name)))
    require(bool(pages), 'No numeric JSON page files found')
    require([n for n, _ in pages] == list(range(1, len(pages) + 1)),
            'Page filenames must be contiguous, starting at 0001.json')
    records = []
    source_files = []
    counts = Counter()
    previous_time = None
    seen_cursors = set()
    display_names = set()
    for page_index, (_, page_path) in enumerate(pages):
        page = load_page(page_path)
        chats = ref_map(page['chats'], f'{page_path.name} chats')
        senders = ref_map(page['senders'], f'{page_path.name} senders')
        require(bool(chats), f'{page_path.name}: no chat mapping')
        require(all(chat.get('chat_guid') == args.chat_guid for chat in chats.values()),
                f'{page_path.name}: contains an unexpected chat')
        for chat in chats.values():
            if isinstance(chat.get('display_name'), str):
                display_names.add(chat['display_name'])
        for sender in senders.values():
            require(isinstance(sender.get('handle'), str),
                    f'{page_path.name}: sender mapping has no handle')
        cursor = page.get('next_cursor')
        if page_index < len(pages) - 1:
            require(isinstance(cursor, str) and bool(cursor),
                    f'{page_path.name}: missing continuation cursor before a later page')
            require(cursor not in seen_cursors, f'{page_path.name}: repeated continuation cursor')
            seen_cursors.add(cursor)
        else:
            require(cursor is None or cursor == '',
                    f'{page_path.name}: final response still has a continuation cursor')
        require(bool(page['messages']) or page_index == len(pages) - 1,
                f'{page_path.name}: empty nonfinal page')
        for position, message in enumerate(page['messages']):
            location = f'{page_path.name} message {position + 1}'
            require(isinstance(message, dict), f'{location}: message must be an object')
            require(isinstance(message.get('chat'), str) and message['chat'] in chats,
                    f'{location}: unknown chat reference')
            when = timestamp(message.get('date'), location)
            require(when < upper, f'{location}: date is outside exclusive upper bound')
            require(previous_time is None or when <= previous_time,
                    f'{location}: source is not in non-increasing timestamp order')
            previous_time = when
            body = message.get('body')
            require(body is None or isinstance(body, str), f'{location}: body is not text/null')
            attachments = message.get('attachments', [])
            require(isinstance(attachments, list), f'{location}: attachments must be an array')
            for attachment in attachments:
                require(isinstance(attachment, dict) and isinstance(attachment.get('id'), str),
                        f'{location}: invalid attachment metadata')
            sender_ref = message.get('sender')
            require(isinstance(sender_ref, str), f'{location}: invalid sender reference')
            if sender_ref == 'me':
                sender_name, handle, service, from_me = args.owner_name, None, None, True
                counts['sent'] += 1
            elif sender_ref == 'unknown':
                sender_name, handle, service, from_me = 'Unknown', None, None, None
                counts['unknown_sender'] += 1
                counts['received'] += 1
            else:
                require(sender_ref in senders, f'{location}: unknown sender reference')
                sender = senders[sender_ref]
                sender_name = sender.get('name') or sender['handle']
                require(isinstance(sender_name, str), f'{location}: invalid sender name')
                handle, service, from_me = sender['handle'], sender.get('service'), False
                counts['received'] += 1
            record = {
                'date': message['date'],
                'timestamp_utc': utc_iso(when),
                'chat_guid': args.chat_guid,
                'sender': sender_name,
                'is_from_me': from_me,
                'sender_handle': handle,
                'sender_service': service,
                'body': body,
                'attachments': attachments,
                'source_page': page_path.name,
                'source_message_index': position,
                'source_traversal_ordinal': len(records),
            }
            if 'is_unread' in message:
                require(isinstance(message['is_unread'], bool), f'{location}: invalid unread flag')
                record['is_unread'] = message['is_unread']
            records.append((when, record))
            counts['total'] += 1
            counts['attachment_items'] += len(attachments)
            counts['messages_with_attachments'] += bool(attachments)
            counts['missing_body'] += body is None
            counts['empty_body'] += body == ''
        source_files.append({'file': page_path.name, 'messages': len(page['messages']),
                             'sha256': sha256(page_path)})
    for key, expected in (('total', args.expected_total), ('sent', args.expected_sent),
                          ('received', args.expected_received)):
        require(counts[key] == expected,
                f'Count mismatch for {key}: expected {expected}, got {counts[key]}')
    records.sort(key=lambda pair: (pair[0], -pair[1]['source_traversal_ordinal']))
    try:
        output.mkdir(mode=0o700, parents=True)
    except FileExistsError:
        require(output.is_dir(), 'Output path must be a directory')
    else:
        os.chmod(output, 0o700)
    require(not output.is_symlink(), 'Output directory must not be a symlink')
    staging = Path(tempfile.mkdtemp(prefix=f'.{output.name}.staging-', dir=output.parent))
    os.chmod(staging, 0o700)
    try:
        jsonl_path = staging / 'messages.jsonl'
        transcript_path = staging / 'transcript.txt'
        with jsonl_path.open('x', encoding='utf-8', newline='\n') as jsonl, \
                transcript_path.open('x', encoding='utf-8', newline='\n') as transcript:
            transcript.write('Messages conversation export\n')
            transcript.write(f'Timestamps: {args.timezone}\n')
            transcript.write('Attachments: metadata only; contents not downloaded\n\n')
            for when, record in records:
                jsonl.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
                local = when.astimezone(local_tz)
                transcript.write(f"[{local.isoformat()} {local.tzname()}] {record['sender']}\n")
                if record['body'] is not None:
                    transcript.write(record['body'] + '\n')
                elif not record['attachments']:
                    transcript.write('[No text body supplied by connector]\n')
                for attachment in record['attachments']:
                    transcript.write('[Attachment metadata only: ' +
                                     json.dumps(attachment, ensure_ascii=False, sort_keys=True) + ']\n')
                transcript.write('\n')
            jsonl.flush()
            os.fsync(jsonl.fileno())
            transcript.flush()
            os.fsync(transcript.fileno())
        summary = {
            'created_at_utc': utc_iso(datetime.now(timezone.utc)),
            'source': 'Local Messages connector read_messages paginated responses',
            'chat_guid': args.chat_guid,
            'chat_display_names': sorted(display_names),
            'exclusive_upper_bound': args.upper_bound,
            'timezone_for_transcript': args.timezone,
            'counts': {key: counts[key] for key in (
                'total', 'sent', 'received', 'unknown_sender', 'attachment_items',
                'messages_with_attachments', 'missing_body', 'empty_body')},
            'resolved_received': counts['received'] - counts['unknown_sender'],
            'received_count_definition': 'All non-me records, including Unknown; Unknown direction is not inferred.',
            'earliest_message_utc': utc_iso(records[0][0]) if records else None,
            'latest_message_utc': utc_iso(records[-1][0]) if records else None,
            'pagination_complete': True,
            'source_pages': source_files,
            'attachments_downloaded': False,
            'deduplication_performed': False,
            'output_files': {path.name: {'sha256': sha256(path), 'bytes': path.stat().st_size}
                             for path in (jsonl_path, transcript_path)},
            'limitations': [
                'Completeness is limited to history available through the local connector.',
                'No stable message ID is exposed; no text-based deduplication was performed.',
                'Cursor continuity cannot be independently proven from response payloads alone; '
                'all nonfinal pages had unique next_cursor values and the final page had none.',
                'Pages were checked newest first; output reverses source traversal order for '
                'equal timestamps. True ordering within timestamp ties cannot be proven.',
                'Parsed ISO timestamps use Python datetime microsecond precision; original '
                'date strings are preserved.',
                'Missing body is preserved as JSON null, distinct from an empty string.',
                'Literal unknown senders are labeled Unknown and their direction remains '
                'unknown; received is defined as non-me for connector count reconciliation.',
                'Attachment metadata is preserved, but attachment contents were not downloaded.',
            ],
        }
        summary_path = staging / 'export-summary.json'
        with summary_path.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        for path in staging.iterdir():
            os.chmod(path, 0o600)
        # Hard-link complete files atomically without replacing any existing path.
        # If a later link fails, remove only links this invocation created.
        linked = []
        try:
            for name in output_names:
                destination = output / name
                os.link(staging / name, destination)
                linked.append(destination)
        except OSError:
            for destination in linked:
                destination.unlink()
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(json.dumps({'status': 'ok', 'messages': counts['total'], 'sent': counts['sent'],
                      'received': counts['received'], 'unknown_sender': counts['unknown_sender'],
                      'pages': len(pages)}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ExportError, OSError) as error:
        # Validation errors contain locations/counts only, never message bodies.
        print(f'Export conversion failed: {error}', file=sys.stderr)
        sys.exit(1)

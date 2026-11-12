# Exporting and exploring a Messages conversation

These workflows produce a local archive and an optional, playful “Messages Wrapped” summary. They do not train a model. The public learning models remain unimplemented.

Start with agreed conversations and keep exports under the ignored `data/private/` directory. Use invented text for parser development and public examples, as described in the [data guide](../data/README.md).

## Make the intended history available

On a Mac, open Messages → Settings → iMessage. If you use Messages in iCloud, choose **Sync Now**, wait for syncing, and check several older messages in the intended conversation. Apple documents these [Messages settings](https://support.apple.com/en-ie/guide/messages/icht39422/mac).

An export reflects the history available to its source. Check the oldest and newest expected messages; a successful export alone does not establish that every message ever exchanged is present.

## Route A: export TXT or HTML with imessage-exporter

[ReagentX’s imessage-exporter](https://github.com/ReagentX/imessage-exporter) is a free, open-source, read-only tool. Its CLI exports TXT or HTML from a Mac Messages database or a supported local iPhone backup.

Install it through [Homebrew](https://formulae.brew.sh/formula/imessage-exporter):

```bash
brew install imessage-exporter
```

Give the terminal app Full Disk Access in System Settings → Privacy & Security → Full Disk Access, then reopen it. Export a participant’s conversations into a local folder:

```bash
imessage-exporter \
  --format txt \
  --copy-method disabled \
  --conversation-filter "<participant-number-or-email>" \
  --export-path data/private/raw/example/txt
```

Replace the placeholder before running. The participant filter also includes group chats containing a match, so inspect the exported conversation files before selecting the intended one-to-one thread. Disabling attachment copying leaves references rather than a self-contained media archive. The tool cannot retrieve history stored only in iCloud. See its [command documentation](https://github.com/ReagentX/imessage-exporter/blob/develop/imessage-exporter/README.md) and [FAQ](https://github.com/ReagentX/imessage-exporter/blob/develop/docs/faq.md).

This route produces readable TXT/HTML. The converter below accepts Messages connector JSON pages; it does not parse these TXT/HTML files.

## Route B: archive one exact chat through the Messages connector

When the Messages connector is available, resolve the conversation once and export only that chat:

1. Call `find_chats` with the intended `participants` and `exact_participants: true`. Confirm the returned participants and retain the stable `chat_guid`.
2. Call `count_message_activity` for that `chat_guid` with `breakdown: "overall"` and `interval: "total"`. Retain the counts and resolved exclusive upper time bound.
3. Call `read_messages` with the exact `chat_guid`, that same `to` bound, and `limit: 100`. Keep any lower bound identical as well if one was selected.
4. Follow each returned `next_cursor` unchanged until the final page has none. Pages arrive newest first. Keep request bounds fixed throughout the export.
5. Save the structured page payloads locally as `0001.json`, `0002.json`, and so on, without printing message contents into logs.

Each page contains its own `chats` and `senders` maps. A message’s `chat` and `sender` references must be resolved against that page’s maps. A sender can also be the literal `me` or `unknown`; page-local references must never be carried into another page.

Suggested layout:

```text
data/private/raw/example/
  source-pages/
    0001.json
    0002.json
```

For illustration, an invented page payload looks like this:

```json
{
  "chats": [{"local_ref": "chat0", "chat_guid": "example-direct-chat"}],
  "senders": [{"local_ref": "sender0", "handle": "person@example.invalid", "name": "Other speaker"}],
  "messages": [
    {"chat": "chat0", "sender": "me", "date": "2026-01-02T18:00:00Z", "body": "Tea after class?"},
    {"chat": "chat0", "sender": "sender0", "date": "2026-01-02T17:59:00Z", "body": "A fictional test message."}
  ]
}
```

Use `scripts/convert_messages_export.py` to validate the pages and create `messages.jsonl`, `transcript.txt`, and `export-summary.json`. The following command uses **invented counts for a four-record example**. Replace the chat ID, bounds, and all three counts with values from the actual count request; they are validation inputs, not defaults:

```bash
python3 scripts/convert_messages_export.py \
  --source-dir data/private/raw/example/source-pages \
  --output-dir data/private/raw/example \
  --chat-guid '<resolved-chat-guid>' \
  --expected-total 4 \
  --expected-sent 2 \
  --expected-received 2 \
  --upper-bound '<ISO-8601-exclusive-bound>' \
  --owner-name Me
```

The converter preserves every record, multiline text, Unicode, original timestamps, and available attachment metadata. It checks chat scope, counts, reference resolution, timestamp order, and pagination completion. Existing output files are not overwritten.

Important interpretation limits:

- Unknown senders retain an unknown direction. For count reconciliation, the received count means all records whose sender is not `me`, including unknown entries.
- The connector does not expose stable message IDs. The converter does not deduplicate by message text: identical-looking messages can be legitimate separate entries.
- Equal timestamps are ordered by reversing source traversal order. That is deterministic, but the precise original order within ties cannot be proven from this schema.
- Attachment metadata is retained; attachment contents are not downloaded. A missing body remains JSON `null` rather than becoming an empty string.
- Unique continuation cursors and a terminal page are checked; saved responses alone cannot independently prove which cursor was used for every request.

## Optional: make a Messages Wrapped summary

Run the separate analysis tool against the explicit JSONL export:

```bash
python3 scripts/messages_wrapped.py \
  data/private/raw/example/messages.jsonl \
  --output data/private/processed/wrapped.json \
  --timezone America/Los_Angeles \
  --term 'good morning' \
  --term babe \
  --emoji '🫶' \
  --game-title Chess
```

The summary describes combined activity, calendar patterns, selected phrases, tracked emoji appearances, attachments, and selected exact game-title labels. Repeated `--term` and `--emoji` options replace their respective generic defaults; game titles are tracked only when supplied with `--game-title`. Activity counts include exported reaction and app entries. Text statistics exclude recognized generated reaction captions so quoted text is not counted again. Selected emoji counts are appearances, not an overall popularity ranking; game-title counts are not verified games played or wins.

Keep the tone friendly: shared habits and rituals are useful material for a fun recap. Message volume, phrase frequency, or response behavior does not establish who cares more about a relationship. Review any generated graphic before sharing it, including its numbers, spellings, and identifying details.

## GUI alternative and backup completeness

[iMazing’s export guide](https://imazing.com/guides/how-to-export-iphone-text-messages-sms-and-imessages-to-your-computer-as-pdf-excel-csv-or-rsmf) describes exporting selected iPhone conversations to CSV or TXT on Mac or Windows. It is a paid alternative with a limited trial. If using a computer backup, verify its actual contents: Apple states that backups exclude data already synced and stored in iCloud, including messages. See [Apple’s backup documentation](https://support.apple.com/en-us/108771). Do not assume an arbitrary backup contains a complete chat archive.

## Before using an archive for the project

The JSONL archive intentionally preserves source identifiers and metadata for fidelity. It is not a sanitized training corpus. A separate preparation step still needs stable anonymous speaker labels, conversation/session boundaries, metadata removal, and a chronological evaluation split. Start that work with synthetic conversations and follow the [roadmap](ROADMAP.md).

Keep raw pages, transcripts, structured exports, personal summaries, generated graphics, and any future weights trained on personal data in ignored local directories. Check `git diff --cached` before publishing; an ignore rule does not protect a file already tracked by Git.

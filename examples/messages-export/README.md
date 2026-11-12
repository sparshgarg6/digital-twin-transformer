# Invented Messages export

These four records, identifiers, and attachment metadata are invented. There is no attachment file. They demonstrate a complete two-page connector export with different page-local references, Unicode, and multiline text.

Run from the repository root with Python 3.11 or later:

```bash
python3 scripts/convert_messages_export.py \
  --source-dir examples/messages-export/source-pages \
  --output-dir data/private/raw/demo \
  --chat-guid demo-direct-chat \
  --expected-total 4 \
  --expected-sent 2 \
  --expected-received 2 \
  --upper-bound 2026-01-03T00:00:00Z \
  --owner-name Me \
  --timezone UTC

python3 scripts/messages_wrapped.py \
  data/private/raw/demo/messages.jsonl \
  --output data/private/processed/demo-wrapped.json \
  --timezone UTC \
  --term 'good morning' \
  --term friend \
  --emoji '☕' \
  --game-title Chess
```

The recap should contain four records on one active calendar date, two occurrences of “good morning,” one tracked coffee emoji, and one exact `Chess` game-title message. Expected counts refer to this fixture only. Both commands refuse to overwrite existing output by default; choose a fresh output path when repeating the example.

See the [export guide](../../docs/IMESSAGE_EXPORT.md) for actual archive preparation and the [Wrapped guide](../../docs/MESSAGES_WRAPPED.md) for interpreting counts and generating a graphic.

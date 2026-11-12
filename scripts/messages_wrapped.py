#!/usr/bin/env python3
"""Create combined statistics from an explicitly supplied local Messages JSONL export.

This dependency-free tool does not connect to Messages or open its live database.
Both input and output paths must be supplied explicitly. Keep private summaries
in ignored data/ or artifacts/ folders when working in this public repository.
All text analysis is combined; speaker names and chat identifiers are not emitted.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "America/Los_Angeles"
DEFAULT_TERMS = ("good morning", "good night", "goodnight")
DEFAULT_EMOJIS = ("❤️", "😂", "✨")
WORD_PATTERN = re.compile(r"\b\w+(?:['’]\w+)*\b", re.UNICODE)
QUOTED_BODY = r'(?:“[\s\S]*”|"[\s\S]*")'
MEDIA_DESCRIPTION = (
    r"(?:(?:a|an) (?:image|photo|video|movie|audio message|sticker|attachment|"
    r"link|location|contact|message|handwritten message|Digital Touch message))"
)
REACTION_PATTERNS = {
    "standard_tapback": re.compile(
        r"(?:Loved|Liked|Disliked|Laughed at|Emphasized|Questioned)\s+(?:"
        + QUOTED_BODY + "|" + MEDIA_DESCRIPTION + ")"
    ),
    "custom_reaction": re.compile(
        r"Reacted\s+.+?\s+to\s+(?:" + QUOTED_BODY + "|" + MEDIA_DESCRIPTION + ")",
        re.DOTALL,
    ),
    "removed_reaction": re.compile(
        r"Removed\s+.+?\s+from\s+(?:" + QUOTED_BODY + "|" + MEDIA_DESCRIPTION + ")",
        re.DOTALL,
    ),
}


class WrappedError(ValueError):
    """An input or output validation error that does not disclose message text."""


def parse_timestamp(value: object, record_number: int) -> datetime:
    if not isinstance(value, str):
        raise WrappedError(f"Record {record_number}: expected an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise WrappedError(f"Record {record_number}: invalid ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise WrappedError(f"Record {record_number}: timestamp needs a timezone")
    return parsed.astimezone(timezone.utc)


def read_jsonl(path: Path) -> Iterable[Mapping[str, object]]:
    """Read only this explicit file; never search for message data."""
    if path.suffix.lower() != ".jsonl":
        raise WrappedError("Input must be an explicit .jsonl export file")
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise WrappedError(f"Input line {line_number}: invalid JSON") from None
            if not isinstance(record, dict):
                raise WrappedError(f"Input line {line_number}: expected a JSON object")
            yield record


def classify_reaction_caption(body: str) -> str | None:
    """Recognize full caption shapes, including attachment placeholders.

    This is a format heuristic, not a determination of message provenance. A
    human-authored message with exactly the same shape cannot be distinguished.
    """
    candidate = body.replace("\ufffc", "").strip()
    for kind, pattern in REACTION_PATTERNS.items():
        if pattern.fullmatch(candidate):
            return kind
    return None


def normalize_choices(values: Sequence[str], *, case_insensitive: bool = False) -> list[str]:
    choices = []
    seen = set()
    for value in values:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise WrappedError("Configured terms, emoji strings, and titles must not be empty")
        key = cleaned.casefold() if case_insensitive else cleaned
        if key not in seen:
            seen.add(key)
            choices.append(cleaned)
    return choices


def leaders(counter: Counter) -> dict:
    count = max(counter.values(), default=0)
    return {"count": count, "values": [str(key) for key in sorted(counter) if counter[key] == count]}


def longest_streak(active_days: Iterable[date]) -> dict:
    best_length = 0
    best_ranges = []
    previous = None
    run_start = None
    run_length = 0
    for day in sorted(set(active_days)):
        if previous is not None and day == previous + timedelta(days=1):
            run_length += 1
        else:
            run_start, run_length = day, 1
        if run_length > best_length:
            best_length, best_ranges = run_length, [(run_start, day)]
        elif run_length == best_length:
            best_ranges.append((run_start, day))
        previous = day
    return {
        "days": best_length,
        "ranges": [{"start": start.isoformat(), "end": end.isoformat()}
                   for start, end in best_ranges],
    }


def analyze_records(
    records: Iterable[Mapping[str, object]],
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    terms: Sequence[str] = DEFAULT_TERMS,
    emojis: Sequence[str] = DEFAULT_EMOJIS,
    game_titles: Sequence[str] = (),
) -> dict:
    """Aggregate exported records without retaining identities or message bodies."""
    try:
        local_zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise WrappedError("Unknown timezone; supply an installed IANA timezone name") from None
    terms = normalize_choices(terms, case_insensitive=True)
    emojis = normalize_choices(emojis)
    game_titles = normalize_choices(game_titles)
    term_patterns = {
        term: re.compile(
            r"(?<!\w)" + r"\s+".join(re.escape(word) for word in term.split()) + r"(?!\w)",
            re.IGNORECASE,
        )
        for term in terms
    }
    days, months, hours = Counter(), Counter(), Counter()
    phrase_counts, emoji_counts, game_counts = Counter(), Counter(), Counter()
    reaction_counts = Counter()
    total = words = attachment_items = attached_messages = 0
    missing_bodies = empty_bodies = text_bodies = 0
    first = last = None
    for record_number, record in enumerate(records, 1):
        if not isinstance(record, Mapping):
            raise WrappedError(f"Record {record_number}: expected an object")
        when = parse_timestamp(record.get("date", record.get("timestamp_utc")), record_number)
        local_time = when.astimezone(local_zone)
        first = when if first is None or when < first else first
        last = when if last is None or when > last else last
        body = record.get("body")
        if body is not None and not isinstance(body, str):
            raise WrappedError(f"Record {record_number}: body must be text or null")
        attachments = record.get("attachments", [])
        if not isinstance(attachments, list) or any(not isinstance(item, dict) for item in attachments):
            raise WrappedError(f"Record {record_number}: attachments must be metadata objects in an array")
        total += 1
        days[local_time.date()] += 1
        months[local_time.strftime("%Y-%m")] += 1
        hours[local_time.strftime("%H:00")] += 1
        attachment_items += len(attachments)
        attached_messages += bool(attachments)
        if body is None:
            missing_bodies += 1
            continue
        if body == "":
            empty_bodies += 1
        kind = classify_reaction_caption(body)
        if kind:
            reaction_counts[kind] += 1
            continue
        text_bodies += bool(body)
        words += len(WORD_PATTERN.findall(body))
        for term, pattern in term_patterns.items():
            phrase_counts[term] += len(pattern.findall(body))
        for emoji in emojis:
            emoji_counts[emoji] += body.count(emoji)
        cleaned = body.strip()
        for title in game_titles:
            game_counts[title] += cleaned == title
    first_local = first.astimezone(local_zone) if first else None
    last_local = last.astimezone(local_zone) if last else None
    span = (last_local.date() - first_local.date()).days + 1 if first else 0
    return {
        "schema_version": 1,
        "timezone": timezone_name,
        "record_count": total,
        "first_record_local": first_local.isoformat() if first_local else None,
        "last_record_local": last_local.isoformat() if last_local else None,
        "calendar_span_inclusive_days": span,
        "active_days": len(days),
        "active_day_rate": len(days) / span if span else 0.0,
        "longest_consecutive_active_day_streak": longest_streak(days),
        "busiest_day": leaders(days),
        "busiest_month": leaders(months),
        "peak_hour_local": leaders(hours),
        "records_by_month": dict(sorted(months.items())),
        "records_by_hour_local": {f"{hour:02d}:00": hours[f"{hour:02d}:00"] for hour in range(24)},
        "word_token_count": words,
        "bodies_used_for_text_metrics": text_bodies,
        "missing_body_records": missing_bodies,
        "empty_body_records": empty_bodies,
        "records_with_attachments": attached_messages,
        "attachment_metadata_items": attachment_items,
        "reaction_captions_excluded_from_text_metrics": sum(reaction_counts.values()),
        "reaction_caption_types": dict(sorted(reaction_counts.items())),
        "phrase_counts": {term: phrase_counts[term] for term in terms},
        "tracked_emoji_appearances": {emoji: emoji_counts[emoji] for emoji in emojis},
        "game_title_body_matches": {title: game_counts[title] for title in game_titles},
        "methods": {
            "scope": "Combined aggregates only; no speaker comparisons or response-time calculations.",
            "records": "Every exported record is counted, including reactions, game updates, missing bodies and duplicates. No deduplication.",
            "activity": "Local calendar dates with any record are active; streaks require adjacent dates. Activity counts retain reaction captions.",
            "words": r"Unicode regex \b\w+(?:['’]\w+)*\b; numbers, URL fragments and underscores can be tokens. Missing bodies and attachments contribute no tokens.",
            "phrases": "Case-insensitive whole-word/whole-phrase matches; whitespace between words may vary. Overlapping configured phrases are not additive; elongated variants are excluded.",
            "reaction_captions": {
                "matching": "Case-sensitive full-body matching after deleting U+FFFC attachment placeholders and stripping outer whitespace; bodies are not changed.",
                "patterns": {name: pattern.pattern for name, pattern in REACTION_PATTERNS.items()},
                "effect": "Excluded from word, phrase, emoji and title metrics; retained in record/activity counts.",
                "limitation": "This is a caption-shape heuristic; human-authored text in exactly the same shape is indistinguishable.",
            },
            "emoji": "Literal substring appearances of configured Unicode strings, in configuration order. A base emoji may match within a modified or joined sequence, and selections may overlap. This is neither a complete emoji total nor an overall ranking.",
            "game_titles": "Exact case-sensitive body equality after stripping outer whitespace; title labels are not evidence of games played, wins or outcomes.",
            "attachments": "Metadata entries only; attachment contents are not read or downloaded.",
            "source_limitations": "Completeness depends on the supplied export. Sender identity is ignored, including unknown senders; records are retained. Timestamps are parsed at Python datetime microsecond precision.",
        },
    }


def validate_output_path(output: Path, source: Path) -> Path:
    if output.is_symlink():
        raise WrappedError("Output file must not be a symlink")
    resolved = output.resolve()
    if resolved == source.resolve():
        raise WrappedError("Output must differ from input")
    if resolved.suffix.lower() != ".json":
        raise WrappedError("Output must have a .json extension")
    return resolved


def create_private_parents(path: Path) -> None:
    """Create missing directories with private permissions; leave existing ones alone."""
    missing = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise


def write_summary(summary: dict, output: Path, *, force: bool = False) -> None:
    """Publish a complete file atomically, without replacing an existing file by default."""
    if output.is_symlink():
        raise WrappedError("Output file must not be a symlink")
    if output.exists() and not force:
        raise WrappedError("Output already exists; use --force to replace it")
    create_private_parents(output.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".messages-wrapped-", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if force:
            os.replace(temporary, output)
        else:
            try:
                os.link(temporary, output)
            except FileExistsError:
                raise WrappedError("Output already exists; use --force to replace it") from None
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Explicit path to a local converter .jsonl export")
    parser.add_argument("--output", required=True, type=Path, help="Explicit JSON output path; prefer ignored data/ or artifacts/")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE, help="IANA timezone for calendar/hour statistics")
    parser.add_argument("--term", action="append", help="Repeatable phrase; replaces the default greeting terms")
    parser.add_argument("--emoji", action="append", help="Repeatable literal emoji string; replaces defaults")
    parser.add_argument("--game-title", action="append", default=[], help="Repeatable exact game-title body label")
    parser.add_argument("--force", action="store_true", help="Allow replacing the specified summary file")
    args = parser.parse_args(argv)
    try:
        output = validate_output_path(args.output, args.input)
        if output.exists() and not args.force:
            raise WrappedError("Output already exists; use --force to replace it")
        summary = analyze_records(
            read_jsonl(args.input), timezone_name=args.timezone,
            terms=args.term if args.term is not None else DEFAULT_TERMS,
            emojis=args.emoji if args.emoji is not None else DEFAULT_EMOJIS,
            game_titles=args.game_title,
        )
        write_summary(summary, output, force=args.force)
    except WrappedError as error:
        print(f"Wrapped analysis failed: {error}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        # Do not echo arbitrary file paths or source content in CLI output.
        print("Wrapped analysis failed: unable to read input or write output", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "record_count": summary["record_count"],
                      "active_days": summary["active_days"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

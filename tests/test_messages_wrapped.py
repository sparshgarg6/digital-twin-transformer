"""Synthetic tests only; these fixtures contain no real conversation data."""

import importlib.util
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "messages_wrapped.py"
SPEC = importlib.util.spec_from_file_location("messages_wrapped", MODULE_PATH)
wrapped = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wrapped)


def message(body=None, *, date="2025-01-01T12:00:00Z", **extra):
    return {"date": date, "body": body, "attachments": [], **extra}


class TextMetricsTests(unittest.TestCase):
    def test_generated_captions_are_excluded_but_records_are_retained(self):
        captions = [
            "Loved “gentle morning”",
            "Liked an image",
            "Loved a movie",
            "Reacted 🫶 to “gentle\nmorning”\ufffc",
            "Reacted 🫶 to a Digital Touch message\ufffc",
            "Removed a heart from “gentle morning”",
            "Removed 🫶 from “gentle morning”",
        ]
        stats = wrapped.analyze_records(
            [message(body) for body in captions] + [message("gentle morning 🫶")],
            terms=["gentle morning"], emojis=["🫶"],
        )
        self.assertEqual(stats["record_count"], len(captions) + 1)
        self.assertEqual(stats["reaction_captions_excluded_from_text_metrics"], len(captions))
        self.assertEqual(stats["phrase_counts"], {"gentle morning": 1})
        self.assertEqual(stats["tracked_emoji_appearances"], {"🫶": 1})
        self.assertEqual(stats["word_token_count"], 2)

    def test_quoted_human_text_and_caption_prefixes_are_not_enough(self):
        bodies = [
            "I said “Liked a photo” as a joke.",
            "Loved “tea” yesterday, and I still do.",
            "Reacted 🫶 to “tea” and then made more.",
            "Before lunch: Removed a heart from “tea”",
        ]
        for body in bodies:
            with self.subTest(body=body):
                self.assertIsNone(wrapped.classify_reaction_caption(body))
        stats = wrapped.analyze_records([message(body) for body in bodies])
        self.assertEqual(stats["reaction_captions_excluded_from_text_metrics"], 0)
        self.assertEqual(stats["bodies_used_for_text_metrics"], len(bodies))

    def test_phrase_boundaries_case_whitespace_and_overlaps(self):
        stats = wrapped.analyze_records(
            [message("GOOD\tmorning! morning morningish. café CAFÉ. good morning")],
            terms=["good morning", "morning", "café", "MORNING"], emojis=[],
        )
        self.assertEqual(stats["phrase_counts"], {"good morning": 2, "morning": 3, "café": 2})

    def test_word_tokens_and_literal_emoji_appearances(self):
        stats = wrapped.analyze_records(
            [message("can't let's\na_b 42 ❤️ ❤ 🫶🏽")], terms=[], emojis=["❤️", "❤", "🫶"],
        )
        self.assertEqual(stats["word_token_count"], 4)
        self.assertEqual(stats["tracked_emoji_appearances"], {"❤️": 1, "❤": 2, "🫶": 1})
        self.assertIn("neither a complete emoji total nor an overall ranking", stats["methods"]["emoji"])

    def test_game_labels_are_exact_bodies(self):
        stats = wrapped.analyze_records(
            [message("Chess"), message(" Chess \n"), message("chess"),
             message("Let's play Chess"), message("Liked “Chess”")],
            game_titles=["Chess"],
        )
        self.assertEqual(stats["game_title_body_matches"], {"Chess": 2})

    def test_unknown_senders_duplicates_and_missing_bodies_are_retained(self):
        unknown = message("A synthetic hello", sender="Unknown", is_from_me=None,
                          chat_guid="synthetic-chat")
        stats = wrapped.analyze_records([
            unknown, dict(unknown),
            message(None, attachments=[{"id": "synthetic-one"}, {"id": "synthetic-two"}]),
            message(""),
        ])
        self.assertEqual(stats["record_count"], 4)
        self.assertEqual(stats["word_token_count"], 6)
        self.assertEqual(stats["missing_body_records"], 1)
        self.assertEqual(stats["empty_body_records"], 1)
        self.assertEqual(stats["records_with_attachments"], 1)
        self.assertEqual(stats["attachment_metadata_items"], 2)
        serialized = json.dumps(stats)
        self.assertNotIn("synthetic-chat", serialized)
        self.assertNotIn("A synthetic hello", serialized)
        self.assertNotIn("synthetic-one", serialized)


class CalendarTests(unittest.TestCase):
    def test_local_midnight_month_boundary_and_streak_gap(self):
        stats = wrapped.analyze_records([
            message("first", date="2025-02-01T07:59:59Z"),
            message("second", date="2025-02-01T08:00:00Z"),
            message("third", date="2025-02-03T08:00:00Z"),
        ])
        self.assertEqual(stats["calendar_span_inclusive_days"], 4)
        self.assertEqual(stats["active_days"], 3)
        self.assertEqual(stats["records_by_month"], {"2025-01": 1, "2025-02": 2})
        self.assertEqual(stats["peak_hour_local"], {"count": 2, "values": ["00:00"]})
        self.assertEqual(stats["longest_consecutive_active_day_streak"], {
            "days": 2, "ranges": [{"start": "2025-01-31", "end": "2025-02-01"}],
        })

    def test_empty_input_is_a_valid_empty_summary(self):
        stats = wrapped.analyze_records([])
        self.assertEqual(stats["record_count"], 0)
        self.assertEqual(stats["calendar_span_inclusive_days"], 0)
        self.assertEqual(stats["active_days"], 0)
        self.assertEqual(stats["active_day_rate"], 0)
        self.assertIsNone(stats["first_record_local"])
        self.assertIsNone(stats["last_record_local"])
        self.assertEqual(stats["longest_consecutive_active_day_streak"], {"days": 0, "ranges": []})
        self.assertEqual(stats["busiest_day"], {"count": 0, "values": []})

    def test_timestamp_fallback_and_timezone_validation(self):
        stats = wrapped.analyze_records([{"timestamp_utc": "2025-01-01T12:00:00Z"}])
        self.assertEqual(stats["record_count"], 1)
        with self.assertRaises(wrapped.WrappedError):
            wrapped.analyze_records([message("text", date="2025-01-01T12:00:00")])
        with self.assertRaises(wrapped.WrappedError):
            wrapped.analyze_records([], timezone_name="Not/A_Timezone")


class FileSafetyTests(unittest.TestCase):
    def test_explicit_output_can_be_anywhere_but_cannot_replace_input_or_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.jsonl"
            allowed = root / "chosen-output" / "summary.json"
            self.assertEqual(wrapped.validate_output_path(allowed, source), allowed.resolve())
            with self.assertRaises(wrapped.WrappedError):
                wrapped.validate_output_path(source, source)
            link = root / "linked-output.json"
            link.symlink_to(root / "target.json")
            with self.assertRaises(wrapped.WrappedError):
                wrapped.validate_output_path(link, source)

    def test_atomic_output_refuses_overwrite_until_force(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "summary.json"
            wrapped.write_summary({"version": 1}, output)
            with self.assertRaises(wrapped.WrappedError):
                wrapped.write_summary({"version": 2}, output)
            self.assertEqual(json.loads(output.read_text()), {"version": 1})
            wrapped.write_summary({"version": 2}, output, force=True)
            self.assertEqual(json.loads(output.read_text()), {"version": 2})
            self.assertEqual([path.name for path in output.parent.iterdir()], ["summary.json"])
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(output.parent.stat().st_mode), 0o700)

    def test_malformed_input_error_does_not_echo_source_text(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.jsonl"
            source.write_text('{"body": "invented private text"}\ninvalid invented text\n')
            with self.assertRaisesRegex(wrapped.WrappedError, r"Input line 2: invalid JSON") as error:
                list(wrapped.read_jsonl(source))
            self.assertNotIn("invented", str(error.exception))

    def test_cli_uses_explicit_paths_and_prints_only_aggregate_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.jsonl", root / "chosen" / "summary.json"
            source.write_text(json.dumps(message("Invented secret café ✨")) + "\n")
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = wrapped.main([str(source), "--output", str(output),
                                       "--term", "café", "--emoji", "✨"])
            self.assertEqual(status, 0, stderr.getvalue())
            self.assertEqual(json.loads(stdout.getvalue()), {
                "status": "ok", "record_count": 1, "active_days": 1,
            })
            self.assertNotIn("secret", stdout.getvalue() + stderr.getvalue())
            summary = json.loads(output.read_text())
            self.assertEqual(summary["phrase_counts"], {"café": 1})
            self.assertEqual(summary["tracked_emoji_appearances"], {"✨": 1})


if __name__ == "__main__":
    unittest.main()

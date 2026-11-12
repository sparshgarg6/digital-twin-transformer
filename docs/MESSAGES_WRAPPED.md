# A playful Messages Wrapped

A Messages Wrapped is a recap of a conversation's patterns: activity over time, recurring phrases, tracked emoji, and game-title appearances. It is an optional archive-exploration exercise, separate from model training. [One open-source example](https://github.com/whyisjake/imessage-wrapped) illustrates the format.

Use `scripts/messages_wrapped.py` on the JSONL archive produced by the converter. The [invented example](../examples/messages-export/README.md) shows both commands. Outputs contain combined statistics for the supplied conversation. Repeated `--term` or `--emoji` options replace the corresponding generic defaults. Add `--game-title` for each game label to track; no game titles are selected by default. A tracked symbol's count is not a ranking of every emoji used.

## What the numbers mean

- Activity counts include all exported records, including reactions, attachment-only records, and app/game entries. The available export determines the covered period.
- Daily and hourly statistics use the selected time zone. An active-day streak means at least one record on each local calendar date in the streak.
- Text statistics exclude recognized generated reaction captions, including quoted tapbacks, custom reactions, and removals. English caption recognition is a heuristic; other languages or new caption formats may need updates.
- Phrase matching is case-insensitive and uses word boundaries. Elongated spellings are separate strings.
- Emoji appearance counts use the supplied literal symbols; they do not establish sentiment or intent.
- Game counts match complete message bodies to known titles. They count title appearances rather than verified rounds, wins, or losses.

Review unexpected results against the source before using them in a caption. Message volume and phrase counts describe a chat; they do not measure a relationship.

## Turn reviewed aggregates into a graphic

The image-generation step is manual. There is no image API dependency or automatic upload in these utilities. Start with [the poster prompt template](../examples/wrapped-poster-prompt.txt), replace its placeholders with reviewed aggregate results, and remove any unused blocks. Use an image generator to create the graphic, then check every number, name, and unusual word in the result.

For a friendly shared recap, build jokes around mutual routines, elaborate greetings, repeated words, and game titles. Keep individual reply-speed rankings and speculative relationship verdicts out of this template.

Save personal posters, prompts, and recap outputs under `artifacts/private/` or `data/private/`. A graphic can reveal personal information even when it contains no transcript. The public example contains placeholders and invented messages only.

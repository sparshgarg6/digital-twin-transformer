# Local data

Place corpora and exports here. Everything in this directory except this guide is ignored by Git.

Suggested local layout:

```text
data/
  public/input.txt
  private/raw/
  private/processed/
```

## First corpus

Choose one small public-domain or synthetic text corpus for all three learning sessions. Record its source, usage terms, SHA-256 checksum, character count, vocabulary, and split rule in your experiment notes.

Use a reproducible split, such as the first 90% of the text for training and the final 10% for validation. Construct context windows within each split so they never cross the boundary. Reuse the same corpus and evaluation convention for every baseline.

## Later: message history

Start parser development with invented conversations. Before using real exports, agree with all participants on which messages may be used for this experiment. Copy only the intended export into `private/raw/`; never point an ingestion script at the live Messages database by default.

The planned preparation pipeline should:

- Select the intended participants and text messages; omit attachments initially.
- Replace participant identifiers with stable speaker labels.
- Remove contact details and identifying metadata from the model input.
- Preserve message order, speaker turns, and conversation boundaries.
- Split chronologically by whole conversation before making training windows.
- Keep the target speaker explicit when evaluating reply generation.

Do not mix results on this private corpus with the original public-corpus comparison. Do not publish excerpts from either raw messages or model outputs without reviewing them for copied or identifying content.

No export, parser, corpus, or preprocessing implementation is provided yet.

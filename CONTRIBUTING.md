# Working together

This project is for learning by implementing and explaining the models ourselves.

## Workflow

1. Create a branch for one session or improvement.
2. Work through the relevant session checklist.
3. Record what changed, how it was checked, and any measured results.
4. Open a pull request for the other collaborator to review.

Keep changes small enough to explain together. Treat `model.py` and `train.py`, when created, as the hands-on learning work: write them yourselves, try each part before consulting the lectures, and rewrite anything you cannot explain.

## Before a push

- Check `git diff --cached` for the exact contents being published.
- Keep personal corpora, message exports, checkpoints, and private samples in the ignored directories.
- Report observed results separately from planned features and target metrics.

Do not commit real conversation examples as test fixtures. Use invented text when demonstrating a parser or a conversation format.

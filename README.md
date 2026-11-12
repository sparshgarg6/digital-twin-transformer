# Digital Twin Transformer

A learning project to build a character-level language model from scratch, then explore whether a small conversational model can capture a person's writing style using their own message history.

**Status:** learning scaffold with local Messages export and recap utilities. No models have been implemented or trained, and no personal conversations are included.

## The idea

Start with the mechanics: count character transitions, train a neural network, then implement causal self-attention. Compare each model on the same text before experimenting with a separate, private conversational dataset.

The longer-term experiment is a "digital twin" of someone's messaging style: a model that drafts replies in a similar voice. This is an exploratory goal, not a claim that a tiny transformer can reproduce a person, their knowledge, or their judgment.

## Build in three sessions

| Session | Build | Learn | Suggested time |
| --- | --- | --- | --- |
| [1. Bigram](sessions/01-bigram/README.md) | A next-character predictor based on counts | Tokenization, probabilities, sampling, negative log-likelihood | ~2 hours |
| [2. MLP](sessions/02-mlp/README.md) | A neural predictor with a fixed context window | Embeddings, backpropagation, optimization | ~3 hours |
| [3. Transformer](sessions/03-transformer/README.md) | A small decoder-only transformer | Causal attention, residual connections, positional information | ~3-4 hours |

The initial aspiration is validation loss below roughly **1.5 nats per character**, together with generated text that resembles the source. This is a target, not a reported result; corpus, model size, and training budget affect what is achievable.

## Getting started

Use Python 3.11 or 3.12 with PyTorch. A Mac, CPU, or a Colab GPU can be used; choose the compute device when implementing training.

```bash
git clone https://github.com/sparshgarg6/digital-twin-transformer.git
cd digital-twin-transformer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional device check:

```bash
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.cuda.is_available()); print('MPS:', torch.backends.mps.is_available())"
```

1. Choose a small public or synthetic text corpus and place it under `data/`.
2. Record its source and define a reproducible train/validation split using the [data guide](data/README.md).
3. Start with [Session 1](sessions/01-bigram/README.md). Create the implementation files yourself as you work through each session.
4. Record settings and measurements in the [experiment log](docs/EXPERIMENT_LOG.md).

There is no training command yet. Each session describes the code to write and the behavior to verify.

## Export and explore a conversation locally

The [Messages export guide](docs/IMESSAGE_EXPORT.md) covers Mac TXT/HTML exports, archiving one exact chat through the Messages connector, and checking archive completeness. The included Python utilities use the standard library and operate on explicitly supplied local files:

- `scripts/convert_messages_export.py` validates saved connector pages and writes chronological JSONL, a readable transcript, and an export receipt.
- `scripts/messages_wrapped.py` creates a combined recap of activity, selected phrases, tracked emoji, and game-title appearances.

Try the complete workflow with the [invented example](examples/messages-export/README.md). Personal archives and recaps belong in the ignored `data/` and `artifacts/` directories. The archive preserves source metadata; preparing anonymous training examples remains a separate step.

Run the utility checks without installing PyTorch:

```bash
python3 -m unittest discover -s tests -v
```

## Repository layout

```text
data/                  Local corpora and message exports; contents ignored by Git
artifacts/             Local checkpoints, samples, and run outputs; contents ignored by Git
docs/ROADMAP.md        Learning milestones and the conversational-model experiment
docs/EXPERIMENT_LOG.md  Template for comparable runs
docs/IMESSAGE_EXPORT.md Local archive and optional Wrapped workflow
docs/MESSAGES_WRAPPED.md Recap interpretation and graphic prompt
scripts/               Local export conversion and aggregate recap tools
examples/messages-export/ Invented connector pages for a complete example
tests/                 Utility checks using invented messages
sessions/01-bigram/     Counting baseline
sessions/02-mlp/        Fixed-context neural model
sessions/03-transformer/ Causal transformer
```

## Personal conversation experiments

Keep the public learning experiment separate from the private message experiment. Export utilities are available; the roadmap still covers training-data preparation, speaker identity, conversation boundaries, and evaluation on later conversations. Begin with synthetic conversations before using any real messages.

Raw exports, identifying metadata, private generated samples, and weights trained on personal messages belong in the ignored `data/` and `artifacts/` directories. The original planning documents and chat screenshots are not part of this repository. A Git ignore rule prevents normal staging; it does not remove anything already committed.

See [the roadmap](docs/ROADMAP.md) and [contribution guide](CONTRIBUTING.md) for the next steps.

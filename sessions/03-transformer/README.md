# Session 3: Causal transformer

**Goal:** implement a small decoder-only transformer for next-character prediction. Suggested time: ~3-4 hours.

## Work through

- [ ] Reuse the same corpus, vocabulary, and split as the earlier sessions.
- [ ] Create token and position embeddings.
- [ ] Implement scaled dot-product attention with a causal mask.
- [ ] Add multiple attention heads, feed-forward layers, residual connections, and normalization.
- [ ] Train with shifted next-character targets and cross-entropy.
- [ ] Evaluate in inference mode and generate within the supported context length.
- [ ] Compare loss and samples with the bigram and MLP.
- [ ] Record what the model does well, what fails, and whether the loss target is reached.

Create `model.py` and `train.py` here as the hands-on implementation.

## Explain and check

Trace the query, key, value, and attention-score shapes. Why scale the dot product? Change only a future token and check that earlier output logits do not change in evaluation mode. Can the model overfit a tiny batch? Do evaluation and sampling disable dropout?

## Lecture

Andrej Karpathy: [Let's build GPT: from scratch, in code, spelled out](https://www.youtube.com/watch?v=kCc8FmEb1nY).

After this works, move to the [conversational experiment](../../docs/ROADMAP.md).

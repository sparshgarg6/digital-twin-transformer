# Session 2: Fixed-context MLP

**Goal:** learn next-character probabilities from several preceding characters. Suggested time: ~3 hours.

## Work through

- [ ] Reuse the first session's corpus, vocabulary, and split.
- [ ] Construct context/target pairs separately inside each split.
- [ ] Implement embeddings, a hidden layer, and output logits.
- [ ] Train using cross-entropy and gradient-based optimization.
- [ ] Evaluate without updating parameters and sample autoregressively.
- [ ] Compare loss and generated text with the counting baseline.
- [ ] Record the configuration and results in the experiment log.

Create `model.py` and `train.py` here as the hands-on implementation.

## Explain and check

Trace every tensor shape. Why pass logits to cross-entropy? Can the model overfit a tiny training batch? Does validation leave parameters unchanged? How does the context length affect parameter count and available information?

## Lectures

- Andrej Karpathy: [The spelled-out intro to neural networks and backpropagation: building micrograd](https://www.youtube.com/watch?v=VMj-3S1tku0)
- Andrej Karpathy: [Building makemore Part 2: MLP](https://www.youtube.com/watch?v=TCH_1BHY58I)

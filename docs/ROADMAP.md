# Roadmap

## 1. Understand the foundations

- [ ] Select one public or synthetic corpus and fix the evaluation split.
- [ ] Implement the counting bigram and record held-out loss and a sample.
- [ ] Implement the MLP and compare it with the bigram.
- [ ] Implement the causal transformer and compare it with both baselines.
- [ ] Explain each component and investigate whether the ~1.5 validation-loss target is attainable on the chosen corpus.

Use the same text for these three models. Keep the original learning task small enough to work through by hand.

## 2. Define the conversational experiment

**Question:** Can a small model trained from scratch draft held-out replies that reflect a target speaker's style?

This stage starts after the learning models work. It is a separate experiment with its own corpus and evaluation. A low character-level loss alone does not establish useful conversational behavior.

- [ ] Agree on the target speaker, allowed data, and a small first use case.
- [ ] Define a synthetic conversation fixture with stable speaker labels and clear turn boundaries.
- [ ] Choose an explicit input/output format for a conversation prefix and the target speaker's next reply.
- [x] Document local export routes and validate connector-page conversion with invented fixtures.
- [x] Add a separate combined Messages Wrapped utility for optional archive exploration.
- [ ] Build a training-data preparation step against a synthetic conversation fixture.
- [ ] Prepare an agreed message export locally; exclude attachments initially.
- [ ] Reserve later, whole conversations for evaluation before constructing training windows.
- [ ] Compare the model against simple baselines, such as common replies and retrieved training replies.

Local archive conversion and aggregate exploration are implemented. The anonymous training format, session boundaries, and any changes to the training objective remain design work.

## 3. Evaluate before building an interface

- [ ] Measure held-out next-character loss on the conversational corpus.
- [ ] Review replies for style, relevance to the preceding turns, repetition, and unwanted speaker switching.
- [ ] Check whether generated replies copy long training passages or reveal identifying details.
- [ ] Record data size, model size, training budget, and failure cases.
- [ ] Decide whether more from-scratch training is useful or whether a separate pretrained-model experiment is warranted.

A conversational draft should be clearly presented as model output. Automatic sending is outside the current scope.

## Optional extensions

Only after the text experiment works: caption drafting from a separate writing corpus, conditioning on explicit context, and eventually image-related experiments. These are ideas, not implemented features or commitments.

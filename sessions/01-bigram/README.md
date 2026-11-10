# Session 1: Counting bigram

**Goal:** predict the next character from the current character using counts. No neural network is needed. Suggested time: ~2 hours.

## Work through

- [ ] Read the chosen corpus and define a character-to-index mapping and its inverse.
- [ ] Set aside validation text before counting training transitions.
- [ ] Count adjacent character pairs and turn counts into next-character probabilities.
- [ ] Handle unseen transitions with smoothing.
- [ ] Sample a sequence one character at a time.
- [ ] Compute mean negative log-likelihood on held-out next-character predictions.
- [ ] Record the baseline in the experiment log.

Create the implementation here when you start. There is no generated solution or training entry point in this scaffold.

## Explain and check

Why must each probability row sum to one? What happens when a transition has zero probability? Does smoothing use training counts only? Can you calculate the loss of a tiny example by hand and match the implementation?

## Lecture

Try the work first, then use Andrej Karpathy's [Building makemore Part 1: Bigram](https://www.youtube.com/watch?v=PaCmpygFfXo) to check your understanding.

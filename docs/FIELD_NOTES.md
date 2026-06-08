# Field Notes

## Problem

Many entrepreneurs write weak headlines that describe a topic but do not communicate why a reader should care. A headline can be short and still fail if it lacks a clear outcome, emotional tension, specificity, or a differentiated angle.

## Small model angle

Headline optimization is a narrow, structured task. The backend can calculate the diagnosis deterministically and ask a small model only for the creative part: three improved headline versions and a winner.

## Design decision

The app now uses a single input: the user's current headline. It does not ask for optional context or headline counts. The frontend renders a fixed report so the experience feels like a headline coach rather than a generic chatbot.

## Future work

Test `Qwen/Qwen2.5-1.5B-Instruct` on Hugging Face Spaces, compare the quality of the three model-generated versions against the mock fallback, and keep tightening the prompt while preserving the stable JSON output contract.

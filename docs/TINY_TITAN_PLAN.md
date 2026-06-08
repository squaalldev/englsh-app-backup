# Tiny Titan Plan

## Target model

Headline Booster AI uses this primary small-model target:

```text
Qwen/Qwen2.5-1.5B-Instruct
```

This model is instruction-tuned and small enough for the Build Small / Tiny Titan direction while still being useful for Spanish copywriting tasks when the output is constrained.

## Runtime switch

```bash
MODEL_ID=Qwen/Qwen2.5-1.5B-Instruct
MAX_NEW_TOKENS=280
USE_REAL_MODEL=auto
```

Runtime rules:

- `USE_REAL_MODEL=true`: load and use the Hugging Face model.
- `USE_REAL_MODEL=false`: use the deterministic mock fallback.
- `USE_REAL_MODEL=auto`: use the model when Hugging Face Space environment variables are present; otherwise use mock mode locally.

## Why this fits the app

The product is no longer a generic headline generator. It is a narrow optimizer:

```text
weak headline → deterministic diagnosis → 3 improved versions → mini battle → winner
```

The model only generates:

- three improved versions;
- a winner number from 1 to 3;
- a short explanation of why that winner is strongest.

Everything else is controlled by backend code, which makes the app more stable for a small model.

## Fallback plan

The backend uses the mock fallback if:

- the model does not load;
- generation fails;
- the model returns invalid JSON;
- fewer than three versions are returned;
- the winner number is not 1, 2, or 3.

This keeps the app functional during local development and during Space cold starts.

## Completed implementation

- Added `gradio.Server` backend/API mode in `app.py`.
- Added a short JSON-only model prompt.
- Added deterministic diagnosis scoring.
- Added validation and fallback completion for model output.
- Added the custom `index.html` frontend that calls the backend API.

---
license: mit
title: ' Headline-booster'
sdk: gradio
emoji: 💻
colorFrom: yellow
colorTo: yellow
pinned: true
sdk_version: 6.17.3
---
# Headline Booster AI

Headline Booster AI is a small-model-ready headline optimizer for Hugging Face Spaces. The app takes one weak headline and returns a fixed, structured improvement report: diagnosis, missing elements, three stronger versions, a mini battle, and one winner.

## What it does

The user pastes a single headline, for example:

```text
Aprende Diseño Humano
```

The app now works in three conversational steps:

1. First it analyzes the headline as a radiography: what it has, what it does not have, and what it needs.
2. Then it asks whether the user wants three improved headline proposals.
3. After creating the proposals, it asks where the headline will be used so it can choose the best winner for that context.

## How to run locally

```bash
pip install -r requirements.txt
USE_REAL_MODEL=false python app.py
```

Then open the local URL printed by Gradio, usually `http://127.0.0.1:7860`.

## API

### `GET /health`

Returns runtime metadata and confirms that the app is alive.

### `POST /api/analyze_headline`

Returns the headline radiography: scores, what it has, what it lacks, what it needs, and the next question.

### `POST /api/create_proposals`

Returns three improved headline proposals after the user confirms they want them.

### `POST /api/choose_winner`

Receives the headline, the three proposals, and where the user will use it, then returns the recommended winner.

### `POST /api/improve_headline`

Legacy one-shot endpoint kept for compatibility. Request:

```json
{
  "headline": "Titular escrito por el usuario"
}
```

Response shape is stable:

```json
{
  "ok": true,
  "app_build": "headline-optimizer-clean-2026-06-08",
  "runtime": "model",
  "model_id": "Qwen/Qwen2.5-1.5B-Instruct",
  "titular_original": "Titular escrito por el usuario",
  "diagnostico": {
    "claridad": 0,
    "deseo": 0,
    "especificidad": 0,
    "diferenciacion": 0
  },
  "problema_principal": "Explicación breve del principal problema del titular.",
  "falta": ["Elemento 1", "Elemento 2", "Elemento 3", "Elemento 4"],
  "versiones": ["Versión clara", "Versión emocional", "Versión curiosa"],
  "mini_battle": {"mas_claro": 1, "mas_emocional": 2, "mas_curioso": 3},
  "ganador_numero": 1,
  "ganador": "Titular ganador",
  "por_que_gana": "Explicación breve."
}
```

## Architecture

```text
.
├── app.py          # Gradio Server backend/API
├── index.html     # Complete custom frontend: HTML, CSS, and JavaScript
├── requirements.txt
├── README.md
└── docs/
    ├── CODEX_NOTES.md
    ├── COMMIT_LOG.md
    ├── FIELD_NOTES.md
    ├── FRONTEND_REFERENCE_NOTES.md
    └── TINY_TITAN_PLAN.md
```

The visual interface is no longer built with `gr.Blocks()`. `index.html` owns the UI and calls `POST /api/improve_headline` with `fetch()`. Browser history is stored only in `localStorage`; the backend does not persist sessions.

## Hackathon alignment

- Built on Gradio Server for Hugging Face Spaces
- Custom frontend with a single headline input
- Prepared for a small model under 32B parameters
- Tiny Titan target model: `Qwen/Qwen2.5-1.5B-Instruct`
- Mock fallback if the model fails or returns invalid JSON
- No OpenAI, Claude, paid API, database, login, or external generation service

## Runtime configuration

```bash
MODEL_ID=Qwen/Qwen2.5-1.5B-Instruct
MAX_NEW_TOKENS=280
USE_REAL_MODEL=auto
```

Runtime rules:

- `USE_REAL_MODEL=true`: use the Hugging Face model.
- `USE_REAL_MODEL=false`: use the mock fallback.
- `USE_REAL_MODEL=auto`: use the model on Hugging Face Spaces and mock locally.

## Source code

GitHub repo: TODO

## Built with Codex

This app was built with help from OpenAI Codex as a coding agent.

Codex migration evidence is documented in `docs/CODEX_NOTES.md` and `docs/COMMIT_LOG.md`. Visual adaptation notes are documented in `docs/FRONTEND_REFERENCE_NOTES.md`.

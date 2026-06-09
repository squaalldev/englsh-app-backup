# Codex Notes

## How Codex helped

Codex reviewed the existing repository, identified the old React/FastAPI/Supabase/Groq architecture, and reshaped the project into a focused Hugging Face Space called **Headline Booster AI**.

## Repository analysis

The original repository was an English-learning chatbot named COMPARTIR AI. It used a React/Vite frontend, Tailwind custom styling, FastAPI backend routes, Supabase authentication/session storage, external AI-service wiring, and multiple chat components for a broader learning product.

Those pieces did not match the new product goal: a small-model headline optimizer that takes one weak headline and returns a stable structured report.

## Current architecture

- `index.html` owns the complete frontend: HTML, CSS, JavaScript, local browser history, layout, and rendering.
- `app.py` is backend/API only, implemented with `gradio.Server` instead of `gr.Blocks()`.
- Browser history is stored in `localStorage`; the backend does not store sessions.
- The frontend now uses step-based endpoints: `POST /api/analyze_headline`, `POST /api/create_proposals`, and `POST /api/choose_winner`. The one-shot `POST /api/improve_headline` remains for compatibility.

## What was reused

- The product-level idea of a left sidebar plus clean main workspace.
- A warm, minimal visual direction with large rounded inputs and cards.
- The hackathon-oriented tiny-model plan around `Qwen/Qwen2.5-1.5B-Instruct`.

## What was removed

- The old React/Vite application.
- The prior Gradio Blocks visual layer.
- FastAPI backend files from the original app.
- Supabase authentication and protected routes.
- External paid generation APIs.
- English-learning services: translation, grammar correction, vocabulary, roadmap, personalities, speech, login, usage counters, and advanced session flows.
- Backend chat history logic; history is local to each browser.

## Files created or refactored

- `app.py`: Gradio Server backend/API with `/`, `/health`, and `POST /api/improve_headline`.
- `index.html`: complete custom frontend inspired by the reference image.
- `requirements.txt`: Gradio plus optional Tiny Titan runtime dependencies.
- `README.md`: rewritten for the optimizer architecture and Hugging Face Spaces metadata.
- `docs/CODEX_NOTES.md`: documents repository analysis and migration decisions.
- `docs/FIELD_NOTES.md`: documents the product problem, small-model angle, and future work.
- `docs/COMMIT_LOG.md`: records relevant Git commits for hackathon/Codex review.
- `docs/FRONTEND_REFERENCE_NOTES.md`: explains how the image/reference informed the frontend.
- `docs/TINY_TITAN_PLAN.md`: documents the small-model runtime path and fallback behavior.

## Output contract

The backend splits the experience into a guided conversation. It first returns a radiography of the headline, then creates three proposals only after user confirmation, then asks for the intended use before selecting a winner. The model is only asked for the proposal-generation part; diagnosis and winner choice are backend-controlled.

## Current status

Headline Booster AI can run with `python app.py`. Locally, `USE_REAL_MODEL=auto` resolves to mock mode. On Hugging Face Spaces, `USE_REAL_MODEL=auto` resolves to the tiny model path. If model loading or model JSON validation fails, the backend uses the mock fallback so the app does not break.

## Next steps

- Deploy the repository as a Hugging Face Space.
- Test the real `Qwen/Qwen2.5-1.5B-Instruct` path on the Space runtime.
- Compare user-facing quality against the fallback mock and tighten the prompt if needed.

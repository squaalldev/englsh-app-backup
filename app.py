"""Backend/API for Headline Booster AI.

This file intentionally avoids building the visual interface in Python.
The complete frontend lives in index.html and this Gradio Server exposes a
small API for optimizing weak headlines with a tiny-model path plus a safe mock
fallback.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import gradio as gr
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

APP_BUILD = "headline-optimizer-clean-2026-06-08"
INDEX_PATH = Path(__file__).with_name("index.html")
MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "280"))
USE_REAL_MODEL = os.getenv("USE_REAL_MODEL", "auto").strip().lower()
IS_HUGGING_FACE_SPACE = bool(
    os.getenv("SPACE_ID") or os.getenv("SPACE_HOST") or os.getenv("HF_SPACE_ID")
)

RESULT_WORDS = {
    "logra",
    "consigue",
    "aumenta",
    "vende",
    "mejora",
    "crece",
    "convierte",
    "gana",
    "atrae",
    "claridad",
    "clientes",
    "ventas",
    "decisiones",
    "resultado",
    "transforma",
    "aprende",
}
AUDIENCE_MARKERS = {
    "para",
    "emprendedores",
    "emprendedoras",
    "copywriters",
    "coaches",
    "negocios",
    "dueños",
    "mujeres",
    "creadores",
    "profesionales",
    "equipos",
}
EMOTION_MARKERS = {
    "sin",
    "miedo",
    "duda",
    "confianza",
    "claro",
    "fácil",
    "rápido",
    "urgente",
    "secreto",
    "evita",
    "dolor",
    "bloqueo",
    "agotamiento",
    "tranquilidad",
}
DIFFERENTIATION_MARKERS = {
    "aunque",
    "sin",
    "método",
    "sistema",
    "paso",
    "guía",
    "nuevo",
    "diferente",
    "probado",
    "desde",
    "en",
}
WEAK_PREFIXES = (
    "aprende",
    "curso de",
    "taller de",
    "mentoría de",
    "guía de",
    "descubre",
    "cómo",
    "como",
    "webinar de",
)


class HeadlineRequest(BaseModel):
    headline: str


def should_use_real_model() -> bool:
    """Resolve runtime mode from USE_REAL_MODEL and Space environment."""
    if USE_REAL_MODEL == "true":
        return True
    if USE_REAL_MODEL == "false":
        return False
    return IS_HUGGING_FACE_SPACE


def clean_headline(headline: str) -> str:
    cleaned = re.sub(r"\s+", " ", (headline or "").strip())
    return cleaned[:260]


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]+", text.lower())


def clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))


def has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def diagnose_headline(headline: str) -> dict[str, int]:
    """Deterministically score headline quality without model dependence."""
    words = word_tokens(headline)
    word_count = len(words)
    lower = headline.lower()

    clarity = 35
    if 4 <= word_count <= 14:
        clarity += 30
    elif 15 <= word_count <= 22:
        clarity += 18
    elif word_count > 22:
        clarity += 6
    if any(word in RESULT_WORDS for word in words):
        clarity += 12
    if re.search(r"[?¿]", headline):
        clarity += 4
    if word_count <= 3:
        clarity -= 15

    desire = 28
    if any(word in RESULT_WORDS for word in words):
        desire += 24
    if any(word in EMOTION_MARKERS for word in words):
        desire += 20
    if "sin " in lower or "para " in lower:
        desire += 10
    if has_number(headline):
        desire += 6

    specificity = 25
    if any(word in AUDIENCE_MARKERS for word in words):
        specificity += 24
    if has_number(headline):
        specificity += 20
    if word_count >= 7:
        specificity += 12
    if any(token in lower for token in ("para ", "en ", "con ", "desde ")):
        specificity += 10

    differentiation = 25
    if any(word in DIFFERENTIATION_MARKERS for word in words):
        differentiation += 18
    if re.search(r"[?¿]", headline):
        differentiation += 18
    if "sin " in lower or "aunque " in lower:
        differentiation += 20
    if any(word in EMOTION_MARKERS for word in words):
        differentiation += 10
    if has_number(headline):
        differentiation += 8

    return {
        "claridad": clamp_score(clarity),
        "deseo": clamp_score(desire),
        "especificidad": clamp_score(specificity),
        "diferenciacion": clamp_score(differentiation),
    }


def detect_main_problem(headline: str, diagnostico: dict[str, int]) -> str:
    weakest = min(diagnostico, key=diagnostico.get)
    explanations = {
        "claridad": "El titular todavía no comunica con suficiente rapidez qué obtiene la persona al seguir leyendo.",
        "deseo": "El titular necesita conectar mejor con un deseo, alivio o transformación concreta para resultar más atractivo.",
        "especificidad": "El titular es demasiado amplio: falta una audiencia, situación o resultado más concreto.",
        "diferenciacion": "El titular suena genérico y necesita un ángulo más distintivo para no parecerse a cualquier otra promesa.",
    }
    if len(word_tokens(headline)) <= 3:
        return "El titular es muy corto y deja demasiadas preguntas abiertas sobre beneficio, audiencia y razón para hacer clic."
    return explanations[weakest]


def missing_elements(headline: str, diagnostico: dict[str, int]) -> list[str]:
    words = set(word_tokens(headline))
    lower = headline.lower()
    items: list[str] = []

    if not any(word in RESULT_WORDS for word in words):
        items.append("Un resultado deseado que la persona pueda imaginar de inmediato.")
    if not any(word in AUDIENCE_MARKERS for word in words):
        items.append("Una audiencia o situación concreta para que el mensaje se sienta dirigido.")
    if not any(word in EMOTION_MARKERS for word in words):
        items.append("Tensión emocional: dolor, deseo, alivio, urgencia o una objeción clara.")
    if not ("sin " in lower or "aunque " in lower or re.search(r"[?¿]", headline)):
        items.append("Un ángulo diferenciador que prometa una forma distinta de lograr el resultado.")
    if not has_number(headline) and diagnostico["especificidad"] < 70:
        items.append("Más concreción: número, plazo, mecanismo, paso o contexto específico.")

    defaults = [
        "Una promesa más directa que explique por qué vale la pena leer ahora.",
        "Un lenguaje menos genérico y más orientado a beneficio.",
        "Un contraste entre la situación actual y el resultado esperado.",
        "Una razón clara para elegir esta solución frente a otras opciones.",
    ]
    for item in defaults:
        if len(items) >= 4:
            break
        if item not in items:
            items.append(item)

    return items[:4]


def headline_topic(headline: str) -> str:
    text = clean_headline(headline)
    lowered = text.lower()
    for prefix in WEAK_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip(" :.-") or text
    return text.strip(" :.-") or "tu idea"


def mock_model_payload(headline: str) -> dict[str, Any]:
    """Generate varied safe fallback copy for any weak headline."""
    original = clean_headline(headline)
    topic = headline_topic(original)
    short_topic = topic[:90]

    versions = [
        f"{short_topic}: consigue un resultado más claro sin complicarte",
        f"Deja de comunicar {short_topic.lower()} como algo genérico y conviértelo en una promesa que se sienta deseable",
        f"¿Y si {short_topic.lower()} fuera justo el cambio que tu audiencia necesita para avanzar?",
    ]
    return {
        "versiones": versions,
        "ganador_numero": 1,
        "por_que_gana": "Gana porque comunica el tema con una promesa más clara, directa y fácil de entender en pocos segundos.",
    }


def build_model_prompt(headline: str) -> str:
    return (
        "Eres un copywriter especialista en titulares. Responde SOLO JSON válido, "
        "sin markdown ni texto adicional. No diagnostiques ni puntúes. Genera exactamente "
        "3 versiones mejoradas del titular: una clara/directa, una emocional y una curiosa. "
        "Elige ganador_numero como 1, 2 o 3 y explica brevemente por qué gana.\n\n"
        "Formato obligatorio:\n"
        '{"versiones":["versión clara/directa","versión emocional","versión curiosa"],'
        '"ganador_numero":1,"por_que_gana":"explicación breve"}\n\n'
        f"Titular original: {headline}"
    )


@lru_cache(maxsize=1)
def get_tiny_model() -> tuple[Any, Any, Any]:
    """Load tokenizer/model lazily only when the real runtime is selected."""
    torch = importlib.import_module("torch")
    transformers = importlib.import_module("transformers")
    tokenizer = transformers.AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = transformers.AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
        trust_remote_code=True,
    )
    if not torch.cuda.is_available():
        model.to("cpu")
    model.eval()
    return tokenizer, model, torch


def extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL)
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Model response did not contain JSON")
    return json.loads(match.group(0))


def _generate_model_payload(headline: str) -> dict[str, Any]:
    tokenizer, model, torch = get_tiny_model()
    prompt = build_model_prompt(headline)
    messages = [
        {"role": "system", "content": "Responde únicamente JSON válido."},
        {"role": "user", "content": prompt},
    ]
    if hasattr(tokenizer, "apply_chat_template"):
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        rendered = prompt
    inputs = tokenizer(rendered, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            temperature=None,
            top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated_ids = output_ids[0][inputs["input_ids"].shape[-1] :]
    response_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return extract_json_object(response_text)


def maybe_gpu(func):
    if importlib.util.find_spec("spaces") is None:
        return func
    spaces_module = importlib.import_module("spaces")
    return spaces_module.GPU(duration=90)(func)


generate_model_payload = maybe_gpu(_generate_model_payload)


def validate_model_payload(candidate: dict[str, Any], headline: str) -> dict[str, Any]:
    fallback = mock_model_payload(headline)
    raw_versions = candidate.get("versiones") if isinstance(candidate, dict) else None
    versions = [str(item).strip() for item in raw_versions or [] if str(item).strip()]

    if len(versions) < 3:
        versions = (versions + fallback["versiones"])[:3]
    else:
        versions = versions[:3]

    try:
        winner = int(candidate.get("ganador_numero", fallback["ganador_numero"]))
    except (TypeError, ValueError):
        winner = fallback["ganador_numero"]
    if winner not in (1, 2, 3):
        winner = fallback["ganador_numero"]

    reason = str(candidate.get("por_que_gana") or "").strip()
    if len(reason) < 12:
        reason = fallback["por_que_gana"]

    return {"versiones": versions, "ganador_numero": winner, "por_que_gana": reason}


def model_or_mock_payload(headline: str) -> tuple[dict[str, Any], str]:
    if not should_use_real_model():
        return validate_model_payload(mock_model_payload(headline), headline), "mock"

    try:
        model_payload = generate_model_payload(headline)
        return validate_model_payload(model_payload, headline), "model"
    except Exception:
        return validate_model_payload(mock_model_payload(headline), headline), "mock"


def improve_headline(headline: str) -> dict[str, Any]:
    titular = clean_headline(headline)
    if not titular:
        raise ValueError("headline is required")

    diagnostico = diagnose_headline(titular)
    problema = detect_main_problem(titular, diagnostico)
    falta = missing_elements(titular, diagnostico)
    generated, runtime = model_or_mock_payload(titular)
    versiones = generated["versiones"]
    ganador_numero = generated["ganador_numero"]
    ganador = versiones[ganador_numero - 1]

    return {
        "ok": True,
        "app_build": APP_BUILD,
        "runtime": runtime,
        "model_id": MODEL_ID,
        "titular_original": titular,
        "diagnostico": diagnostico,
        "problema_principal": problema,
        "falta": falta,
        "versiones": versiones,
        "mini_battle": {"mas_claro": 1, "mas_emocional": 2, "mas_curioso": 3},
        "ganador_numero": ganador_numero,
        "ganador": ganador,
        "por_que_gana": generated["por_que_gana"],
    }


server = gr.Server(
    title="Headline Booster AI",
    description="Small-model headline optimizer API for Hugging Face Spaces.",
)


@server.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    if not INDEX_PATH.exists():
        raise HTTPException(status_code=500, detail="index.html not found")
    return HTMLResponse(INDEX_PATH.read_text(encoding="utf-8"))


@server.get("/health")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "app_build": APP_BUILD,
            "runtime_mode": USE_REAL_MODEL,
            "uses_model_now": should_use_real_model(),
            "model_id": MODEL_ID,
        }
    )


@server.post("/api/improve_headline")
def improve_headline_endpoint(payload: HeadlineRequest) -> JSONResponse:
    try:
        result = improve_headline(payload.headline)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


if __name__ == "__main__":
    server.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        quiet=False,
        _frontend=False,
    )

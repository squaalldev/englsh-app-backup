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
ANALYSIS_MODE = os.getenv("ANALYSIS_MODE", "hybrid").strip().lower()
if ANALYSIS_MODE not in {"rules", "model", "hybrid"}:
    ANALYSIS_MODE = "hybrid"
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

VAGUE_TOPIC_WORDS = {"curso", "taller", "clase", "programa", "mentoría", "guía", "aprende", "descubre"}
BENEFIT_MARKERS = RESULT_WORDS | {"ahorra", "domina", "resuelve", "multiplica", "mejor", "más", "menos"}
SPECIFIC_DETAIL_MARKERS = AUDIENCE_MARKERS | {"en", "con", "desde", "pasos", "días", "semanas", "método", "sistema"}
CURIOSITY_MARKERS = {"?", "¿", "secreto", "error", "mito", "verdad", "nadie", "inesperado", "contrario", "aunque", "sin"}

SYSTEM_PROMPT = """
Eres Headline Booster AI, copywriter experto en mejorar titulares, hooks y líneas de asunto en español.

BASE DE COPY:
Usa fórmulas y principios de copywriting como AIDA, PAS, BAB/ADP, 4Ps, FAB, 4U, StoryBrand, curiosity gap, reframe, contraste, beneficio vs característica, especificidad, emocionalidad, claridad y curiosidad.

OBJETIVO:
Analizar un titular débil y convertirlo en 3 versiones más claras, creíbles, atractivas y naturales.

REGLAS:
- Mejora el titular existente; no inventes otra oferta.
- Usa fórmulas de copywriting como criterio estratégico interno, no como plantillas visibles.
- No rellenes moldes literales.
- Evita frases genéricas, exageradas o robóticas.
- Sé breve, específico, natural y persuasivo.
- No expliques las fórmulas.
- No menciones fórmulas ni frameworks.
- No uses markdown.
- Responde SOLO JSON válido.
- El campo "versiones" debe ser una lista de 3 strings. No uses objetos dentro de "versiones". No incluyas "version", "tipo", "por_que_gana" ni explicaciones dentro de cada versión.
- Si recibes diagnostico, problema_principal o falta, úsalos como guía: baja claridad corrige claridad, bajo deseo eleva deseo, baja especificidad concreta más, baja diferenciacion crea un ángulo propio.

ANÁLISIS RAYOS X:
Evalúa el titular con 4 criterios de 0 a 100:
1. claridad: si se entiende rápido y comunica una promesa reconocible.
2. deseo: si despierta interés emocional, deseo, alivio o identificación.
3. especificidad: si aterriza audiencia, resultado, situación o detalle concreto.
4. diferenciacion: si tiene curiosidad, contraste, reframe o un ángulo propio.

Luego detecta:
- problema_principal: una frase breve.
- falta: lista breve de 3 a 4 elementos.

CREA EXACTAMENTE 3 VERSIONES:
1. Una versión más clara/directa.
2. Una versión más emocional.
3. Una versión más curiosa/diferenciada.

Elige el ganador por fuerza general: claridad + deseo + curiosidad + credibilidad.

FORMATO:
{"diagnostico":{"claridad":0,"deseo":0,"especificidad":0,"diferenciacion":0},"problema_principal":"","falta":["","",""],"versiones":["titular 1","titular 2","titular 3"],"ganador_numero":1,"por_que_gana":""}
""".strip()


class HeadlineRequest(BaseModel):
    headline: str


class ProposalRequest(BaseModel):
    headline: str


class WinnerRequest(BaseModel):
    headline: str
    versiones: list[str]
    usage: str


_MODEL_ANALYSIS_CACHE: dict[str, tuple[dict[str, Any], str]] = {}


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
    """Compact deterministic X-ray score for four persuasive criteria."""
    words = word_tokens(headline)
    word_set = set(words)
    word_count = len(words)
    lower = headline.lower()

    names_topic_only = word_count <= 4 and not any(token in lower for token in ("para ", "sin ", "con ", "en "))
    has_benefit = any(word in BENEFIT_MARKERS for word in word_set) or any(
        token in lower for token in ("para ", "sin ", "mejor", "más", "menos")
    )
    has_emotion = any(word in EMOTION_MARKERS for word in word_set) or any(
        token in lower for token in ("deja de", "evita", "siente", "miedo", "duda", "frustr")
    )
    has_specific = has_number(headline) or any(word in SPECIFIC_DETAIL_MARKERS for word in word_set)
    has_angle = any(marker in lower for marker in CURIOSITY_MARKERS) or bool(re.search(r"[?¿]", headline))
    has_audience = any(word in AUDIENCE_MARKERS for word in word_set)
    vague_count = sum(1 for word in word_set if word in VAGUE_TOPIC_WORDS)

    clarity = 30
    if 5 <= word_count <= 14:
        clarity += 28
    elif 15 <= word_count <= 22:
        clarity += 18
    elif word_count <= 4:
        clarity -= 12
    if has_benefit:
        clarity += 24
    if vague_count and not has_benefit:
        clarity -= 10
    if names_topic_only:
        clarity -= 12

    desire = 25
    if has_emotion:
        desire += 30
    if has_benefit:
        desire += 16
    if any(word in word_set for word in {"alivio", "confianza", "claridad", "ventas", "clientes"}):
        desire += 10
    if names_topic_only:
        desire -= 10

    specificity = 24
    if has_audience:
        specificity += 24
    if has_specific:
        specificity += 22
    if has_number(headline):
        specificity += 12
    if word_count >= 8:
        specificity += 8
    if names_topic_only:
        specificity -= 12

    differentiation = 24
    if has_angle:
        differentiation += 28
    if "sin " in lower or "aunque " in lower:
        differentiation += 16
    if any(word in word_set for word in {"método", "sistema", "secreto", "error", "mito"}):
        differentiation += 12
    if not has_angle and names_topic_only:
        differentiation -= 10

    return {
        "claridad": clamp_score(clarity),
        "deseo": clamp_score(desire),
        "especificidad": clamp_score(specificity),
        "diferenciacion": clamp_score(differentiation),
    }


def detect_main_problem(headline: str, diagnostico: dict[str, int]) -> str:
    if len(word_tokens(headline)) <= 4:
        return "El titular dice el tema, pero no dice por qué debería importarle a la persona."

    weakest = min(diagnostico, key=diagnostico.get)
    explanations = {
        "claridad": "El titular no comunica con suficiente claridad qué cambio promete.",
        "deseo": "El titular dice algo, pero no despierta suficiente interés emocional.",
        "especificidad": "El titular es demasiado general y no aterriza para quién es ni qué resultado ofrece.",
        "diferenciacion": "El titular se entiende, pero suena genérico y necesita un ángulo más propio.",
    }
    return explanations[weakest]


def missing_elements(headline: str, diagnostico: dict[str, int]) -> list[str]:
    words = set(word_tokens(headline))
    lower = headline.lower()
    items: list[str] = []

    if diagnostico["claridad"] < 62:
        items.append("Una promesa más clara")
    if not any(word in BENEFIT_MARKERS for word in words):
        items.append("Un resultado concreto")
    if diagnostico["especificidad"] < 62 or not any(word in AUDIENCE_MARKERS for word in words):
        items.append("Una audiencia más definida")
    if diagnostico["deseo"] < 62 or not any(word in EMOTION_MARKERS for word in words):
        items.append("Una situación emocional reconocible")
    if diagnostico["diferenciacion"] < 62:
        items.append("Un ángulo menos genérico")
    if not ("?" in headline or "¿" in headline or "secreto" in lower or "error" in lower):
        items.append("Más curiosidad")
    if not ("sin " in lower or "aunque " in lower):
        items.append("Un contraste más fuerte")
    if len(word_tokens(headline)) <= 4:
        items.append("Una razón para seguir leyendo")

    fallback_items = [
        "Un resultado concreto",
        "Una audiencia más definida",
        "Una razón para seguir leyendo",
        "Una promesa más clara",
    ]
    unique: list[str] = []
    for item in items + fallback_items:
        if item not in unique:
            unique.append(item)
        if len(unique) >= 4:
            break
    return unique[:4] if len(unique) >= 4 else unique


def headline_strengths(headline: str, diagnostico: dict[str, int]) -> list[str]:
    words = set(word_tokens(headline))
    strengths: list[str] = []
    if any(word in BENEFIT_MARKERS for word in words):
        strengths.append("Tiene una intención o beneficio inicial.")
    if any(word in AUDIENCE_MARKERS for word in words):
        strengths.append("Incluye una señal de audiencia.")
    if has_number(headline) or any(word in SPECIFIC_DETAIL_MARKERS for word in words):
        strengths.append("Aporta algún detalle específico.")
    if re.search(r"[?¿]", headline) or any(marker in headline.lower() for marker in CURIOSITY_MARKERS):
        strengths.append("Tiene una señal de curiosidad o contraste.")
    if not strengths:
        strengths.append("Tiene una idea base simple para mejorar.")
    return strengths[:4]


def headline_absences(headline: str, diagnostico: dict[str, int]) -> list[str]:
    missing = missing_elements(headline, diagnostico)
    mapping = {
        "Una promesa más clara": "No comunica una promesa reconocible.",
        "Un resultado concreto": "No muestra un resultado concreto.",
        "Una audiencia más definida": "No deja claro para quién es.",
        "Una situación emocional reconocible": "No conecta con síntoma, frustración o deseo.",
        "Un ángulo menos genérico": "No tiene un ángulo propio.",
        "Más curiosidad": "No da una razón clara para seguir leyendo.",
        "Un contraste más fuerte": "No plantea contraste o tensión.",
        "Una razón para seguir leyendo": "No explica por qué debería importarle al lector.",
    }
    return [mapping.get(item, item) for item in missing[:4]]


def analyze_headline(headline: str) -> dict[str, Any]:
    titular = clean_headline(headline)
    if not titular:
        raise ValueError("headline is required")
    payload, runtime = cached_model_or_rules_analysis(titular)
    diagnostico = payload["diagnostico"]
    falta = payload["falta"]
    return {
        "ok": True,
        "app_build": APP_BUILD,
        "step": "analisis",
        "runtime": runtime,
        "analysis_mode": ANALYSIS_MODE,
        "model_id": MODEL_ID,
        "titular_original": titular,
        "diagnostico": diagnostico,
        "radiografia": {
            "tiene": headline_strengths(titular, diagnostico),
            "no_tiene": headline_absences(titular, diagnostico),
            "le_hace_falta": falta,
        },
        "problema_principal": payload["problema_principal"],
        "falta": falta,
        "pregunta_siguiente": "¿Quieres que cree tres propuestas de titulares mejorados a partir de esta radiografía?",
    }


def generate_proposals(headline: str) -> dict[str, Any]:
    titular = clean_headline(headline)
    if not titular:
        raise ValueError("headline is required")
    payload, runtime = cached_model_or_rules_analysis(titular)
    return {
        "ok": True,
        "app_build": APP_BUILD,
        "step": "propuestas",
        "runtime": runtime,
        "analysis_mode": ANALYSIS_MODE,
        "model_id": MODEL_ID,
        "titular_original": titular,
        "versiones": payload["versiones"],
        "pregunta_siguiente": "¿Para qué lo quieres o dónde lo vas a usar? Así puedo ayudarte a escoger el mejor.",
    }


def choose_winner(headline: str, versiones: list[str], usage: str) -> dict[str, Any]:
    titular = clean_headline(headline)
    clean_versions = [extract_version_text(item) for item in versiones]
    clean_versions = [item for item in clean_versions if item][:3]
    if not titular:
        raise ValueError("headline is required")
    if len(clean_versions) < 3:
        clean_versions = (clean_versions + mock_model_payload(titular)["versiones"])[:3]
    uso = clean_headline(usage) or "uso general"
    lower_usage = uso.lower()

    if any(word in lower_usage for word in ("anuncio", "ads", "landing", "web", "venta", "checkout", "página")):
        winner = 1
        reason = "Para ese uso gana la versión más clara, porque reduce fricción y comunica rápido qué obtiene la persona."
    elif any(word in lower_usage for word in ("instagram", "redes", "email", "correo", "story", "historia", "comunidad")):
        winner = 2
        reason = "Para ese canal gana la versión emocional, porque conecta mejor con deseo, tensión y sensación de identificación."
    elif any(word in lower_usage for word in ("blog", "youtube", "newsletter", "contenido", "post", "artículo")):
        winner = 3
        reason = "Para contenido gana la versión curiosa, porque abre una pregunta y aumenta las ganas de seguir leyendo."
    else:
        winner = 1
        reason = "Gana la versión más clara porque es la más segura para un uso general: comunica el tema y la promesa con menos esfuerzo."

    return {
        "ok": True,
        "app_build": APP_BUILD,
        "step": "ganador",
        "titular_original": titular,
        "usage": uso,
        "versiones": clean_versions,
        "mini_battle": {"mas_claro": 1, "mas_emocional": 2, "mas_curioso": 3},
        "ganador_numero": winner,
        "ganador": clean_versions[winner - 1],
        "por_que_gana": reason,
    }


def headline_topic(headline: str) -> str:
    text = clean_headline(headline)
    lowered = text.lower()
    for prefix in WEAK_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip(" :.-") or text
            break
    if text.lower().startswith("a "):
        text = text[2:].strip()
    return text.strip(" :.-") or "tu idea"


def _title_case_topic(topic: str) -> str:
    if not topic:
        return "Tu idea"
    return topic[0].upper() + topic[1:]


def mock_model_payload(headline: str) -> dict[str, Any]:
    """Fallback copy using strategic angles without visible rigid templates."""
    topic = headline_topic(headline)[:90]
    display_topic = _title_case_topic(topic)
    lower_topic = topic.lower()
    variant = sum(ord(char) for char in topic) % 3

    clear_options = [
        f"{display_topic} con una promesa clara y fácil de elegir",
        f"{display_topic} para avanzar con más claridad desde el primer paso",
        f"{display_topic} explicado de forma simple, útil y aplicable",
    ]
    emotional_options = [
        f"Menos dudas, más confianza para empezar con {lower_topic}",
        f"La forma más simple de sentir avance real con {lower_topic}",
        f"Convierte la confusión alrededor de {lower_topic} en claridad práctica",
    ]
    curious_options = [
        f"Lo que cambia cuando {lower_topic} deja de ser solo una idea",
        f"La diferencia entre conocer {lower_topic} y usarlo de verdad",
        f"El giro que hace que {lower_topic} se vuelva más claro y útil",
    ]

    versions = [
        clear_options[variant],
        emotional_options[(variant + 1) % 3],
        curious_options[(variant + 2) % 3],
    ]
    return {
        "versiones": versions,
        "ganador_numero": 1,
        "por_que_gana": "Gana porque combina claridad, beneficio y credibilidad sin sonar exagerado.",
    }


def build_model_prompt(
    headline: str,
    diagnostico: dict[str, int] | None = None,
    problema_principal: str | None = None,
    falta: list[str] | None = None,
) -> str:
    payload: dict[str, Any] = {"titular_original": headline}
    if diagnostico is not None:
        payload["diagnostico"] = diagnostico
    if problema_principal:
        payload["problema_principal"] = problema_principal
    if falta:
        payload["falta"] = falta[:4]
    return json.dumps(payload, ensure_ascii=False)


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


def _generate_model_payload(
    headline: str,
    diagnostico: dict[str, int] | None = None,
    problema_principal: str | None = None,
    falta: list[str] | None = None,
) -> dict[str, Any]:
    tokenizer, model, torch = get_tiny_model()
    user_prompt = build_model_prompt(headline, diagnostico, problema_principal, falta)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    if hasattr(tokenizer, "apply_chat_template"):
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        rendered = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
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


def extract_version_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("version", "titular", "headline", "text", "texto"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    return str(item).strip()


def validate_model_payload(candidate: dict[str, Any], headline: str) -> dict[str, Any]:
    fallback = mock_model_payload(headline)
    raw_versions = candidate.get("versiones") if isinstance(candidate, dict) else None
    versions: list[str] = []
    for item in raw_versions or []:
        version = extract_version_text(item).strip().strip('"')
        if not version:
            continue
        lower = version.lower()
        forbidden_tokens = ("aida", "pas", "storybrand", "4ps", "fab", "copywriting", "por_que_gana")
        visible_templates = ("el secreto detrás", "razones por las que", "x razones", "deja de [", "aprende a [", "¿y si [", "{'version':", '{"version":')
        if any(token in lower for token in forbidden_tokens + visible_templates):
            continue
        if "[" in version or "]" in version or len(version) > 180:
            continue
        versions.append(version)

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
    if len(reason) < 12 or any(token in reason.lower() for token in ("aida", "pas", "storybrand", "4ps", "fab")):
        reason = fallback["por_que_gana"]
    if len(reason) > 220:
        reason = reason[:217].rstrip() + "..."

    return {"versiones": versions, "ganador_numero": winner, "por_que_gana": reason}


def validate_diagnostico(candidate: Any, fallback: dict[str, int]) -> dict[str, int]:
    if not isinstance(candidate, dict):
        return fallback
    validated: dict[str, int] = {}
    for key in ("claridad", "deseo", "especificidad", "diferenciacion"):
        try:
            value = int(float(candidate[key]))
        except (KeyError, TypeError, ValueError):
            return fallback
        if value < 0 or value > 100:
            return fallback
        validated[key] = value
    return validated


def validate_brief_text(value: Any, fallback: str, max_length: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    forbidden = ("aida", "pas", "storybrand", "4ps", "fab", "copywriting", "```", "#")
    if len(text) < 8 or any(token in text.lower() for token in forbidden):
        return fallback
    if len(text) > max_length:
        return text[: max_length - 3].rstrip() + "..."
    return text


def validate_missing_list(candidate: Any, fallback: list[str]) -> list[str]:
    if not isinstance(candidate, list):
        return fallback[:4]
    clean_items: list[str] = []
    for item in candidate:
        text = validate_brief_text(item, "", max_length=90)
        if text and text not in clean_items and "[" not in text and "]" not in text:
            clean_items.append(text)
        if len(clean_items) >= 4:
            break
    if len(clean_items) < 3:
        return fallback[:4]
    return clean_items


def validate_full_model_payload(candidate: dict[str, Any], headline: str) -> dict[str, Any]:
    fallback_diagnostico = diagnose_headline(headline)
    fallback_problem = detect_main_problem(headline, fallback_diagnostico)
    fallback_falta = missing_elements(headline, fallback_diagnostico)
    generated = validate_model_payload(candidate if isinstance(candidate, dict) else {}, headline)

    diagnostico = validate_diagnostico(
        candidate.get("diagnostico") if isinstance(candidate, dict) else None,
        fallback_diagnostico,
    )
    problema = validate_brief_text(
        candidate.get("problema_principal") if isinstance(candidate, dict) else None,
        fallback_problem,
        max_length=180,
    )
    falta = validate_missing_list(
        candidate.get("falta") if isinstance(candidate, dict) else None,
        fallback_falta,
    )

    return {
        "diagnostico": diagnostico,
        "problema_principal": problema,
        "falta": falta,
        "versiones": generated["versiones"],
        "ganador_numero": generated["ganador_numero"],
        "por_que_gana": generated["por_que_gana"],
    }


def model_or_mock_payload(
    headline: str,
    diagnostico: dict[str, int] | None = None,
    problema_principal: str | None = None,
    falta: list[str] | None = None,
) -> tuple[dict[str, Any], str]:
    if not should_use_real_model():
        return validate_model_payload(mock_model_payload(headline), headline), "mock"

    try:
        model_payload = generate_model_payload(headline, diagnostico, problema_principal, falta)
        return validate_model_payload(model_payload, headline), "model"
    except Exception:
        return validate_model_payload(mock_model_payload(headline), headline), "mock"


def model_or_rules_analysis(headline: str) -> tuple[dict[str, Any], str]:
    fallback_diagnostico = diagnose_headline(headline)
    fallback_problem = detect_main_problem(headline, fallback_diagnostico)
    fallback_falta = missing_elements(headline, fallback_diagnostico)

    if ANALYSIS_MODE == "rules" or not should_use_real_model():
        generated, runtime = model_or_mock_payload(headline, fallback_diagnostico, fallback_problem, fallback_falta)
        return {
            "diagnostico": fallback_diagnostico,
            "problema_principal": fallback_problem,
            "falta": fallback_falta,
            "versiones": generated["versiones"],
            "ganador_numero": generated["ganador_numero"],
            "por_que_gana": generated["por_que_gana"],
        }, runtime

    try:
        model_payload = generate_model_payload(headline, fallback_diagnostico, fallback_problem, fallback_falta)
        return validate_full_model_payload(model_payload, headline), "model"
    except Exception:
        generated = validate_model_payload(mock_model_payload(headline), headline)
        return {
            "diagnostico": fallback_diagnostico,
            "problema_principal": fallback_problem,
            "falta": fallback_falta,
            "versiones": generated["versiones"],
            "ganador_numero": generated["ganador_numero"],
            "por_que_gana": generated["por_que_gana"],
        }, "mock"


def cached_model_or_rules_analysis(headline: str) -> tuple[dict[str, Any], str]:
    cache_key = clean_headline(headline).lower()
    if ANALYSIS_MODE != "rules" and cache_key in _MODEL_ANALYSIS_CACHE:
        return _MODEL_ANALYSIS_CACHE[cache_key]
    result, runtime = model_or_rules_analysis(headline)
    if ANALYSIS_MODE != "rules":
        if len(_MODEL_ANALYSIS_CACHE) >= 64:
            _MODEL_ANALYSIS_CACHE.pop(next(iter(_MODEL_ANALYSIS_CACHE)))
        _MODEL_ANALYSIS_CACHE[cache_key] = (result, runtime)
    return result, runtime


def build_full_response(titular: str, payload: dict[str, Any], runtime: str) -> dict[str, Any]:
    versiones = payload["versiones"]
    ganador_numero = payload["ganador_numero"]
    ganador = versiones[ganador_numero - 1]
    return {
        "ok": True,
        "app_build": APP_BUILD,
        "runtime": runtime,
        "analysis_mode": ANALYSIS_MODE,
        "model_id": MODEL_ID,
        "titular_original": titular,
        "diagnostico": payload["diagnostico"],
        "problema_principal": payload["problema_principal"],
        "falta": payload["falta"],
        "versiones": versiones,
        "mini_battle": {"mas_claro": 1, "mas_emocional": 2, "mas_curioso": 3},
        "ganador_numero": ganador_numero,
        "ganador": ganador,
        "por_que_gana": payload["por_que_gana"],
    }


def improve_headline(headline: str) -> dict[str, Any]:
    titular = clean_headline(headline)
    if not titular:
        raise ValueError("headline is required")
    payload, runtime = cached_model_or_rules_analysis(titular)
    return build_full_response(titular, payload, runtime)


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
            "analysis_mode": ANALYSIS_MODE,
            "uses_model_now": should_use_real_model(),
            "model_id": MODEL_ID,
        }
    )


@server.post("/api/analyze_headline")
def analyze_headline_endpoint(payload: HeadlineRequest) -> JSONResponse:
    try:
        result = analyze_headline(payload.headline)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@server.post("/api/create_proposals")
def create_proposals_endpoint(payload: ProposalRequest) -> JSONResponse:
    try:
        result = generate_proposals(payload.headline)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@server.post("/api/choose_winner")
def choose_winner_endpoint(payload: WinnerRequest) -> JSONResponse:
    try:
        result = choose_winner(payload.headline, payload.versiones, payload.usage)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


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

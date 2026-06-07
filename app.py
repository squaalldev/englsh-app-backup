"""Headline Booster: a small-model-ready Gradio chatbot for Spanish headlines.

The current generation function is intentionally mocked so the Space does not
require external AI APIs. Replace `generate_headlines_mock` with a local/ZeroGPU
inference function when Qwen2.5-3B-Instruct is added.
"""

from __future__ import annotations

import re
from typing import Any

import gradio as gr


MISSING_INFO_MESSAGE = """Claro. Para crear mejores encabezados necesito solo 4 datos:

1. ¿Qué vendes?
2. ¿Para quién es?
3. ¿Qué resultado quiere conseguir esa persona?
4. ¿Cuántos encabezados quieres?"""

STYLE_LABELS = {
    "default": "claros y persuasivos",
    "emotional": "más emocionales",
    "direct": "más directos",
    "elegant": "más elegantes",
    "curious": "más curiosos",
}

STYLE_HEADLINES = {
    "default": [
        "Deja de decidir desde la duda y empieza a elegir con claridad",
        "Tu cuerpo ya sabe qué decisión tomar. Aprende a escucharlo",
        "Si cada decisión te agota, quizá no estás decidiendo desde ti",
        "Toma decisiones con más confianza sin exigirte funcionar como los demás",
        "Descubre una forma más clara de entender tu energía antes de elegir",
        "Elige con más calma, claridad y confianza desde tu propio diseño",
        "Si tomar decisiones te pesa, quizá necesitas una forma distinta de escucharte",
        "Aprende a reconocer cuándo una decisión sí es para ti",
        "Deja de compararte y empieza a tomar decisiones desde tu energía",
        "Tu claridad no está afuera: empieza a escucharla desde ti",
    ],
    "emotional": [
        "Vuelve a confiar en esa voz interna que sabe lo que necesitas elegir",
        "Deja de sentirte perdida cada vez que una decisión importante aparece",
        "Tu claridad merece más espacio que tus dudas",
        "Elige desde tu energía y recupera la calma que tanto necesitas",
        "No estás confundida: solo necesitas una forma más tuya de decidir",
        "Convierte la presión de decidir en una sensación real de confianza",
        "Escúchate con más amor antes de exigirte respuestas perfectas",
        "Cuando decides desde ti, la duda deja de mandar",
        "Encuentra paz en tus decisiones sin compararte con nadie más",
        "La claridad que buscas puede empezar en tu propio cuerpo",
    ],
    "direct": [
        "Aprende a tomar mejores decisiones usando tu Diseño Humano",
        "Decide con más claridad sin depender de consejos externos",
        "Un taller práctico para emprendedoras que quieren elegir con confianza",
        "Usa tu energía para saber qué decisión tomar",
        "Deja de dudar y empieza a decidir con un método claro",
        "Toma decisiones de negocio alineadas con tu forma de funcionar",
        "Descubre cómo decidir con más calma en menos tiempo",
        "Convierte tu Diseño Humano en una guía práctica para elegir",
        "Mejora tus decisiones entendiendo tu energía personal",
        "Decide con seguridad sin copiar la estrategia de otras personas",
    ],
    "elegant": [
        "Una forma más consciente de decidir desde tu propia naturaleza",
        "Claridad interior para emprendedoras que desean elegir con confianza",
        "Descubre el arte de tomar decisiones alineadas con tu energía",
        "Decisiones más serenas para una vida y un negocio más coherentes",
        "Aprende a escuchar tu diseño antes de elegir tu siguiente paso",
        "Una guía íntima para decidir con calma, presencia y certeza",
        "Eleva tu manera de decidir comprendiendo cómo funciona tu energía",
        "Elige con sobriedad, claridad y respeto por tu propio ritmo",
        "Tu diseño puede convertirse en brújula para decisiones más conscientes",
        "Menos ruido externo. Más claridad desde tu propia energía",
    ],
    "curious": [
        "¿Y si tu cuerpo ya supiera qué decisión tomar?",
        "La razón por la que decidir te agota quizá no es la que crees",
        "¿Estás decidiendo desde tu energía o desde la presión?",
        "El mapa interno que puede cambiar cómo eliges en tu negocio",
        "Antes de pedir otro consejo, escucha esta señal de tu diseño",
        "¿Por qué algunas decisiones se sienten tan pesadas para ti?",
        "La forma de decidir que quizá nadie te enseñó",
        "¿Y si la claridad no estuviera en pensar más?",
        "Lo que tu Diseño Humano puede revelar antes de tu próxima decisión",
        "¿Tus decisiones son tuyas o aprendiste a copiarlas?",
    ],
}

CUSTOM_CSS = """
:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --border: #e5e7eb;
  --text: #111827;
  --muted: #6b7280;
  --primary: #8a5a44;
  --primary-dark: #6f4635;
  --accent: #8b5cf6;
  --success: #22c55e;
}

.gradio-container {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
  min-height: 100vh;
}

#headline-app {
  max-width: 1180px;
  min-height: 92vh;
  margin: 24px auto;
  border: 1px solid var(--border);
  border-radius: 28px;
  overflow: hidden;
  background: var(--surface);
  box-shadow: 0 24px 70px rgba(17, 24, 39, 0.08);
}

#headline-layout { gap: 0; min-height: 92vh; }
#sidebar {
  flex: 0 0 280px !important;
  min-width: 280px !important;
  background: #fbf7f4;
  border-right: 1px solid var(--border);
  padding: 24px 18px;
}
#sidebar h1 { font-size: 24px; line-height: 1.1; margin: 0 0 8px; color: var(--text); }
#sidebar p { color: var(--muted); margin: 0 0 22px; }
.sidebar-card {
  border: 1px solid #eadbd2;
  background: rgba(255,255,255,.72);
  border-radius: 18px;
  padding: 14px;
  margin-top: 18px;
}
.sidebar-title { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 0 0 10px; }
.example-convo {
  padding: 11px 12px;
  border-radius: 14px;
  margin: 8px 0;
  background: var(--surface);
  border: 1px solid transparent;
  color: #374151;
  font-weight: 600;
  font-size: 14px;
}
.example-convo:hover { border-color: #eadbd2; }
#new-chat { width: 100%; }
#new-chat button, #send-btn button {
  background: var(--primary) !important;
  color: #fff !important;
  border: 0 !important;
  border-radius: 16px !important;
  font-weight: 800 !important;
  box-shadow: 0 10px 24px rgba(138, 90, 68, .22) !important;
}
#new-chat button:hover, #send-btn button:hover { background: var(--primary-dark) !important; }

#main-panel { padding: 0; background: var(--surface); min-width: 0; }
.topbar {
  height: 74px;
  padding: 0 28px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.topbar h2 { margin: 0; font-size: 18px; }
.status-wrap { display: flex; align-items: center; gap: 14px; color: var(--muted); font-size: 14px; }
.status-dot { color: var(--success); font-size: 18px; line-height: 0; }
.settings-icon { width: 34px; height: 34px; border: 1px solid var(--border); border-radius: 999px; display: grid; place-items: center; background: #fff; }

#welcome-hero {
  text-align: center;
  padding: 72px 32px 42px;
  max-width: 620px;
  margin: 0 auto;
}
.avatar {
  width: 112px;
  height: 112px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  margin: 0 auto 18px;
  background: linear-gradient(135deg, #fff7ed, #ede9fe);
  border: 1px solid #eadbd2;
  box-shadow: 0 18px 40px rgba(139, 92, 246, .14);
  font-size: 54px;
}
#welcome-hero h2 { font-size: 28px; margin: 0 0 8px; }
#welcome-hero h3 { font-size: 18px; margin: 0 0 10px; color: var(--primary); }
#welcome-hero p { color: var(--muted); font-size: 16px; line-height: 1.65; margin: 0; }

#chatbot { border: 0; padding: 24px 28px 8px; min-height: 455px; }
#chatbot .message-wrap { max-width: 78%; }
#chatbot .user-message { background: var(--primary) !important; color: white !important; border-radius: 18px 18px 4px 18px !important; }
#chatbot .bot-message { background: #fff !important; color: var(--text) !important; border: 1px solid var(--border) !important; border-radius: 18px 18px 18px 4px !important; box-shadow: 0 8px 22px rgba(17, 24, 39, .05); }

.composer {
  border-top: 1px solid var(--border);
  padding: 18px 28px 24px;
  background: linear-gradient(180deg, rgba(255,255,255,.86), #fff);
}
#message-input textarea {
  border-radius: 18px !important;
  border: 1px solid var(--border) !important;
  box-shadow: none !important;
  padding: 14px 16px !important;
  min-height: 58px !important;
}
.helper-text { color: var(--muted); font-size: 12px; margin-top: 8px; }

@media (max-width: 760px) {
  #headline-app { margin: 0; min-height: 100vh; border-radius: 0; border: 0; }
  #headline-layout { flex-direction: column; }
  #sidebar { min-width: 100% !important; flex-basis: auto !important; border-right: 0; border-bottom: 1px solid var(--border); padding: 18px; }
  .sidebar-card { display: none; }
  .topbar { padding: 0 18px; }
  #welcome-hero { padding: 42px 22px 24px; }
  #chatbot { padding: 16px; min-height: 380px; }
  #chatbot .message-wrap { max-width: 92%; }
  .composer { padding: 14px 16px 20px; }
}
"""


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _extract_count(user_message: str) -> int:
    text = _normalize(user_message)
    match = re.search(r"\b(\d{1,2})\b", text)
    if match:
        return max(1, min(int(match.group(1)), 20))

    number_words = {
        "uno": 1,
        "una": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
        "ocho": 8,
        "nueve": 9,
        "diez": 10,
        "once": 11,
        "doce": 12,
    }
    for word, value in number_words.items():
        if re.search(rf"\b{word}\b", text):
            return value
    return 10


def is_request_complete(user_message: str) -> bool:
    """
    Detecta si el usuario ya dio suficiente información.
    Debe usar reglas simples.
    """
    text = _normalize(user_message)
    if len(text.split()) < 10:
        return False

    has_offer = any(
        token in text
        for token in [
            "vendo",
            "ofrezco",
            "tengo",
            "lanzaré",
            "lanzo",
            "curso",
            "taller",
            "mentoría",
            "programa",
            "servicio",
            "web",
        ]
    )
    has_audience = any(
        token in text
        for token in [
            "para ",
            "dirigido a",
            "emprendedoras",
            "emprendedores",
            "coaches",
            "mujeres",
            "dueños",
            "personas que",
        ]
    )
    has_result = any(
        token in text
        for token in [
            "quieren",
            "quiere",
            "buscan",
            "busca",
            "conseguir",
            "lograr",
            "resultado",
            "claridad",
            "confianza",
            "vender",
            "mejorar",
            "tomar decisiones",
        ]
    )
    has_count = bool(re.search(r"\b\d{1,2}\b", text)) or any(
        re.search(rf"\b{word}\b", text)
        for word in ["cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce"]
    )

    return has_offer and has_audience and has_result and has_count


def detect_style_request(user_message: str) -> str:
    """
    Detecta si el usuario pide un ajuste:
    - default
    - emotional
    - direct
    - elegant
    - curious
    """
    text = _normalize(user_message)
    if any(word in text for word in ["emocional", "emocionales", "emotivo", "emotivos", "sentimiento"]):
        return "emotional"
    if any(word in text for word in ["directo", "directos", "claro", "claros", "concreto", "concretos"]):
        return "direct"
    if any(word in text for word in ["elegante", "elegantes", "premium", "sofisticado", "sofisticados"]):
        return "elegant"
    if any(word in text for word in ["curioso", "curiosos", "curiosidad", "intriga", "pregunta"]):
        return "curious"
    return "default"


def generate_headlines_mock(user_message: str, style: str = "default") -> str:
    """
    Genera encabezados simulados en Markdown.
    Luego esta función será reemplazada por inferencia real con un modelo pequeño.
    """
    style = style if style in STYLE_HEADLINES else "default"
    count = _extract_count(user_message)
    headlines = STYLE_HEADLINES[style]
    selected = [headlines[index % len(headlines)] for index in range(count)]
    numbered_headlines = "\n".join(
        f"{index}. {headline}" for index, headline in enumerate(selected, start=1)
    )
    tone_note = STYLE_LABELS[style]

    return f"""## Encabezados generados

{numbered_headlines}

## Mi recomendación

El encabezado #2 es el más fuerte porque combina curiosidad, claridad y una promesa emocional.

## Por qué funciona

Estos encabezados son {tone_note}: conectan la oferta con el resultado deseado y evitan explicar demasiado en la primera línea.

_Nota técnica: esta es una generación mock. La función está preparada para reemplazarse por inferencia local con Qwen2.5-3B-Instruct y ZeroGPU._"""


def _last_complete_user_request(history: list[dict[str, Any]]) -> str:
    for message in reversed(history or []):
        if message.get("role") == "user" and is_request_complete(message.get("content", "")):
            return message.get("content", "")
    return ""


def chat_response(message, history):
    """
    Maneja la conversación.
    Si falta información, pide solo 4 datos.
    Si hay información suficiente, genera encabezados mock.
    Si el usuario pide ajuste de tono, genera una nueva versión mock.
    """
    history = history or []
    clean_message = (message or "").strip()
    if not clean_message:
        return history, "", gr.update(visible=len(history) == 0), history

    style = detect_style_request(clean_message)
    previous_request = _last_complete_user_request(history)
    is_style_adjustment = style != "default" and previous_request and not is_request_complete(clean_message)

    if is_style_adjustment:
        bot_message = generate_headlines_mock(previous_request, style=style)
    elif is_request_complete(clean_message):
        bot_message = generate_headlines_mock(clean_message, style=style)
    else:
        bot_message = MISSING_INFO_MESSAGE

    updated_history = [
        *history,
        {"role": "user", "content": clean_message},
        {"role": "assistant", "content": bot_message},
    ]
    return updated_history, "", gr.update(visible=False), updated_history


def reset_chat():
    """
    Limpia la conversación.
    """
    return [], "", gr.update(visible=True), []


def build_app() -> gr.Blocks:
    with gr.Blocks(css=CUSTOM_CSS, title="Headline Booster", theme=gr.themes.Soft()) as demo:
        chat_state = gr.State([])
        with gr.Column(elem_id="headline-app"):
            with gr.Row(elem_id="headline-layout"):
                with gr.Column(elem_id="sidebar", scale=0, min_width=280):
                    gr.HTML(
                        """
                        <h1>Headline Booster</h1>
                        <p>Encabezados claros. Copy que vende.</p>
                        """
                    )
                    new_chat = gr.Button("+ Nueva conversación", elem_id="new-chat", size="lg")
                    gr.HTML(
                        """
                        <div class="sidebar-card">
                          <div class="sidebar-title">Conversaciones de ejemplo</div>
                          <div class="example-convo">Taller de Diseño Humano</div>
                          <div class="example-convo">Curso de Copywriting</div>
                          <div class="example-convo">Web para Coaches</div>
                          <div class="example-convo">Mentoría para Emprendedoras</div>
                        </div>
                        """
                    )
                with gr.Column(elem_id="main-panel", scale=1):
                    gr.HTML(
                        """
                        <div class="topbar">
                          <h2>Headline Booster</h2>
                          <div class="status-wrap">
                            <span><span class="status-dot">●</span> disponible</span>
                            <span class="settings-icon">⚙</span>
                          </div>
                        </div>
                        """
                    )
                    welcome = gr.HTML(
                        """
                        <section id="welcome-hero">
                          <div class="avatar">🚀</div>
                          <h2>Booster</h2>
                          <h3>Crea encabezados persuasivos en segundos</h3>
                          <p>Dime qué vendes, para quién es, qué resultado prometes y cuántos encabezados quieres.</p>
                        </section>
                        """,
                        visible=True,
                    )
                    chatbot = gr.Chatbot(
                        value=[],
                        elem_id="chatbot",
                        type="messages",
                        show_label=False,
                        height=455,
                        avatar_images=(None, None),
                    )
                    with gr.Column(elem_classes="composer"):
                        with gr.Row():
                            message = gr.Textbox(
                                elem_id="message-input",
                                show_label=False,
                                lines=2,
                                max_lines=6,
                                placeholder="Ej. Vendo un taller de Diseño Humano para mujeres emprendedoras que quieren tomar decisiones con más claridad. Quiero 10 encabezados.",
                                scale=8,
                            )
                            send = gr.Button("Enviar", elem_id="send-btn", variant="primary", scale=1)
                        gr.HTML('<div class="helper-text">Presiona Enter para enviar · Shift+Enter para nueva línea</div>')

        message.submit(
            chat_response,
            inputs=[message, chat_state],
            outputs=[chatbot, message, welcome, chat_state],
        )
        send.click(
            chat_response,
            inputs=[message, chat_state],
            outputs=[chatbot, message, welcome, chat_state],
        )
        new_chat.click(reset_chat, outputs=[chatbot, message, welcome, chat_state])

    return demo


if __name__ == "__main__":
    build_app().launch()

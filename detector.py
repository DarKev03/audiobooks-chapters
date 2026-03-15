"""
detector.py — Detección de capítulos por silencio + confirmación LLM
"""

import ollama
import json
import re

SYSTEM_PROMPT = """Eres un extractor de timestamps. Tu única función es identificar en qué segundo el narrador anuncia un capítulo.
PROHIBIDO: resumir, describir personajes, analizar contenido, añadir claves que no sean "title" y "start_seconds".
OBLIGATORIO: devolver SOLO un JSON array. Si no hay capítulos, devolver [].
Ejemplo correcto: [{"title": "Capítulo 1", "start_seconds": 185.0}]
Ejemplo incorrecto: {"Summary": "...", "Characters": {...}}"""

SILENCE_THRESHOLD = 2.5   # segundos de silencio mínimo antes del anuncio
MAX_CANDIDATE_LENGTH = 60  # caracteres máximos del segmento candidato


def _find_candidates(segments: list[dict]) -> list[dict]:
    """
    Paso 1 — Python puro, sin LLM.
    Devuelve segmentos cortos precedidos de un silencio largo.
    Estos son los únicos candidatos a ser anuncios de capítulo.
    """
    candidates = []
    for i in range(1, len(segments)):
        prev = segments[i - 1]
        curr = segments[i]

        silence = curr["start"] - prev["end"]
        text = curr["text"].strip()

        if silence >= SILENCE_THRESHOLD and len(text) <= MAX_CANDIDATE_LENGTH:
            candidates.append(curr)

    print(f"[Detector] {len(candidates)} candidatos encontrados por silencio+longitud.")
    return candidates


def _build_candidates_text(candidates: list[dict]) -> str:
    """Formatea los candidatos con timestamps para el LLM."""
    return "\n".join(
        f"[{seg['start']:.2f}s] {seg['text'].strip()}"
        for seg in candidates
    )


def _parse_llm_response(response_text: str) -> list[dict]:
    """Extrae y parsea el JSON de la respuesta del LLM."""
    
    # Extraer todos los pares title/start_seconds con regex
    # porque el LLM devuelve JSON inválido con claves duplicadas
    titles = re.findall(r'"title"\s*:\s*"([^"]+)"', response_text)
    timestamps = re.findall(r'"start_seconds"\s*:\s*([\d.]+)', response_text)

    if not titles or not timestamps:
        raise ValueError("No se encontraron títulos o timestamps en la respuesta")

    if len(titles) != len(timestamps):
        raise ValueError(f"Títulos ({len(titles)}) y timestamps ({len(timestamps)}) no coinciden")

    chapters = [
        {"title": title, "start_seconds": float(ts)}
        for title, ts in zip(titles, timestamps)
    ]

    return chapters

def _confirm_with_llm(
    client: ollama.Client,
    model: str,
    candidates: list[dict],
) -> list[dict]:
    """
    Paso 2 — LLM confirma cuáles candidatos son realmente anuncios de capítulo.
    Solo ve textos cortos, sin contenido narrativo, así no se distrae.
    """
    candidates_text = _build_candidates_text(candidates)

    user_message = (
        "De estas líneas, devuelve SOLO las que sean títulos o números de capítulo "
        "leídos por el narrador.\n"
        "IMPORTANTE: devuelve TODOS los capítulos que encuentres, no solo el primero.\n"
        "Ejemplos inválidos: frases normales que contengan números o palabras sueltas sin contexto de capítulo.\n"
        "Si ninguna es un capítulo: []\n\n"
        "LÍNEAS:\n"
        + candidates_text
    )

    print(f"[Detector] Enviando {len(candidates)} candidatos al LLM para confirmar...")

    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        format="json",
        options={"temperature": 0.0},
    )

    raw_text = response["message"]["content"]

    try:
        chapters = _parse_llm_response(raw_text)
        print(f"[Detector] LLM confirmó {len(chapters)} capítulo(s).")  
        return _enrich_titles_from_transcript(chapters, candidates)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[Detector] ⚠️  Error al parsear respuesta del LLM: {e}")
        print(f"[Detector] Respuesta raw:\n{raw_text}")
        print("[Detector] Usando todos los candidatos como fallback.")
        return [
            {"title": seg["text"].strip(), "start_seconds": seg["start"]}
            for seg in candidates
        ]

def _enrich_titles_from_transcript(
    chapters: list[dict],
    segments: list[dict]
) -> list[dict]:
    """Sustituye el título del LLM por el texto real de la transcripción."""
    chapters = chapters.copy()
    for chapter in chapters:
        for segment in segments:
            if segment["text"].strip() == chapter["title"] and segment["start"] != chapter["start_seconds"]:
                chapter["start_seconds"] = segment["start"]
                break
    return chapters

def detect_chapters(
    segments: list[dict],
    model: str = "mistral:7b",
    ollama_host: str = "http://localhost:11434",
    silence_threshold: float = SILENCE_THRESHOLD,
    max_candidate_length: int = MAX_CANDIDATE_LENGTH,
) -> list[dict]:
    """
    Detecta capítulos en dos pasos:
      1. Filtra candidatos por silencio previo y longitud del texto (Python puro)
      2. El LLM confirma cuáles son realmente anuncios de capítulo

    Returns:
        Lista de dicts con keys: title (str), start_seconds (float)
        ordenada por start_seconds.
    """
    client = ollama.Client(host=ollama_host)

    # Paso 1 — filtrado por silencio
    candidates = _find_candidates(segments)

    if not candidates:
        print("[Detector] ⚠️  No se encontraron candidatos. Revisa silence_threshold.")
        return [{"title": "Capítulo 1", "start_seconds": 0.0}]

    # Paso 2 — confirmación LLM
    chapters = _confirm_with_llm(client, model, candidates)

    # Ordenar y deduplicar
    chapters.sort(key=lambda c: c["start_seconds"])
    deduped = []
    for ch in chapters:
        if not deduped or ch["start_seconds"] - deduped[-1]["start_seconds"] > 5.0:
            deduped.append(ch)

    print(f"[Detector] ✅ {len(deduped)} capítulo(s) detectado(s) en total.")
    return deduped
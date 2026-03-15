"""
transcriber.py — Transcripción de audio con Whisper (GPU)
"""

import whisper
import torch
import json
import os


def transcribe(audio_path: str, model_size: str = "medium") -> list[dict]:
    """
    Transcribe el audio con Whisper usando CUDA si está disponible.

    Returns:
        Lista de segmentos con keys: id, start, end, text
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Transcriber] Usando dispositivo: {device.upper()}")
    if device == "cuda":
        print(f"[Transcriber] GPU detectada: {torch.cuda.get_device_name(0)}")

    print(f"[Transcriber] Cargando modelo Whisper '{model_size}'...")
    model = whisper.load_model(model_size, device=device)

    print(f"[Transcriber] Transcribiendo '{os.path.basename(audio_path)}'...")
    result = model.transcribe(
        audio_path,
        language="es",
        word_timestamps=True,
        verbose=False,
    )

    segments = []
    for seg in result["segments"]:
        segments.append({
            "id": seg["id"],
            "start": seg["start"],   # segundos (float)
            "end": seg["end"],       # segundos (float)
            "text": seg["text"].strip(),
        })

    print(f"[Transcriber] {len(segments)} segmentos transcritos.")
    return segments


def save_transcript(segments: list[dict], output_path: str) -> None:
    """Guarda la transcripción en JSON para debug o reutilización."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    print(f"[Transcriber] Transcripción guardada en '{output_path}'")


def load_transcript(path: str) -> list[dict]:
    """Carga una transcripción JSON previamente guardada."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

"""
main.py — Orquestador principal de Chaptr

Uso:
    python main.py <ruta_audio> [opciones]

Ejemplos:
    python main.py libro.mp3
    python main.py libro.m4a --title "El Imperio Final" --author "Brandon Sanderson"
    python main.py libro.mp3 --skip-transcription --transcript transcript.json
    python main.py libro.mp3 --model large --whisper-model large-v3
"""

import argparse
import os
import sys
import time

import transcriber
import detector
import exporter


def parse_args():
    parser = argparse.ArgumentParser(
        description="Chaptr — Añade capítulos automáticos a un audiolibro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("audio", help="Ruta al archivo de audio (MP3, M4A, M4B)")
    parser.add_argument("--output", "-o", help="Ruta del M4B de salida (por defecto: NombreAudio_chapters.m4b)")
    parser.add_argument(
        "--whisper-model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help="Tamaño del modelo Whisper (default: small)",
    )
    parser.add_argument(
        "--llm-model",
        default="mistral:7b",
        help="Modelo Ollama a usar (default: mistral:7b)",
    )
    parser.add_argument( 
        "--ollama-host",
        default="http://localhost:11434",
        help="URL del servidor Ollama (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--skip-transcription",
        action="store_true",
        help="Saltar la transcripción y cargar desde --transcript",
    )
    parser.add_argument(
        "--transcript",
        help="Ruta a un JSON de transcripción previamente guardado",
    )
    parser.add_argument(
        "--save-transcript",
        action="store_true",
        help="Guardar la transcripción como JSON para reutilización futura",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Validación de entrada ──────────────────────────────────────────────
    if not os.path.isfile(args.audio):
        print(f"❌ No se encuentra el archivo: '{args.audio}'")
        sys.exit(1)

    ext = os.path.splitext(args.audio)[1].lower()
    if ext not in (".mp3", ".m4a", ".m4b", ".aac", ".flac", ".wav", ".ogg"):
        print(f"⚠️  Extensión no reconocida: '{ext}'. Intentando de todas formas...")

    # ── Ruta de salida ─────────────────────────────────────────────────────
    if args.output:
        output_path = args.output
    else:
        base = os.path.splitext(args.audio)[0]
        output_path = base + "_chapters.m4b"

    print("=" * 60)
    print("  CHAPTR — Generador de capítulos para audiolibros")
    print("=" * 60)
    print(f"  Entrada : {args.audio}")
    print(f"  Salida  : {output_path}")
    print(f"  Whisper : {args.whisper_model}")
    print(f"  LLM     : {args.llm_model}")
    print("=" * 60)

    t_start = time.time()

    # ── PASO 1: Transcripción ──────────────────────────────────────────────
    if args.skip_transcription:
        if not args.transcript:
            print("❌ --skip-transcription requiere --transcript <ruta.json>")
            sys.exit(1)
        print(f"\n[Paso 1/3] Cargando transcripción desde '{args.transcript}'...")
        segments = transcriber.load_transcript(args.transcript)
        print(f"  ✅ {len(segments)} segmentos cargados.")
    else:
        print(f"\n[Paso 1/3] Transcribiendo audio con Whisper ({args.whisper_model})...")
        t0 = time.time()
        segments = transcriber.transcribe(args.audio, model_size=args.whisper_model)
        print(f"  ✅ Completado en {time.time() - t0:.1f} s")

        if args.save_transcript:
            transcript_path = os.path.splitext(args.audio)[0] + "_transcript.json"
            transcriber.save_transcript(segments, transcript_path)

    # ── PASO 2: Detección de capítulos ────────────────────────────────────
    print(f"\n[Paso 2/3] Detectando capítulos con {args.llm_model} via Ollama...")
    t0 = time.time()
    chapters = detector.detect_chapters(
        segments,
        model=args.llm_model,
        ollama_host=args.ollama_host,
    )
    print(f"  ✅ Completado en {time.time() - t0:.1f} s")

    print("\n  Capítulos detectados:")
    for i, ch in enumerate(chapters):
        m = int(ch["start_seconds"] // 60)
        s = ch["start_seconds"] % 60
        print(f"    {i+1:2d}. [{m:02d}:{s:05.2f}] {ch['title']}")

    # ── PASO 3: Exportar M4B ──────────────────────────────────────────────
    print(f"\n[Paso 3/3] Generando M4B con FFmpeg...")
    t0 = time.time()
    exporter.export_m4b(
        audio_path=args.audio,
        chapters=chapters,
        output_path=output_path,
    )
    print(f"  ✅ Completado en {time.time() - t0:.1f} s")

    # ── Resumen final ──────────────────────────────────────────────────────
    total = time.time() - t_start
    print()
    print("=" * 60)
    print(f"  ✅ ¡COMPLETADO! Tiempo total: {total:.1f} s ({total/60:.1f} min)")
    print(f"  📚 Archivo generado: {output_path}")
    print(f"  📖 Capítulos: {len(chapters)}")
    print("=" * 60)
    print()
    print("  Pasa el M4B a tu iPhone via Finder → sección Libros")
    print("  o arrástralo a la app Libros en tu Mac.")
    print()


if __name__ == "__main__":
    main()

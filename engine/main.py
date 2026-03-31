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
import json

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
        "--json-mode",
        action="store_true",
        help="Salida en formato JSON para integración con interfaces gráficas",
    )
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Solo detecta capítulos y devuelve el JSON final (no genera M4B)",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Genera el M4B usando capítulos y metadatos proporcionados (no detecta nada)",
    )
    parser.add_argument(
        "--chapters-json",
        help="JSON de capítulos para el modo --export-only (string o ruta de archivo)",
    )
    parser.add_argument("--title", help="Título del audiolibro")
    parser.add_argument("--author", help="Autor del audiolibro")
    parser.add_argument("--cover", help="Ruta a la imagen de portada (JPG/PNG)")
    return parser.parse_args()


def report_progress(type, message, step=None, percent=None, json_mode=False):
    """
    Emite el progreso. Si json_mode es True, imprime una línea JSON.
    Si no, imprime texto legible para humanos.
    """
    if json_mode:
        data = {"type": type, "message": message}
        if step is not None:
            data["step"] = step
        if percent is not None:
            data["percent"] = percent
        print(json.dumps(data), flush=True)
    else:
        if type == "progress":
            prefix = f"[{step}/3]" if step else " - "
            print(f"{prefix} {message}")
        elif type == "header":
            print("=" * 60)
            print(f"  {message}")
            print("=" * 60)
        elif type == "success":
            print(f"  ✅ {message}")
        elif type == "error":
            print(f"❌ {message}")
        elif type == "info":
            print(f"  {message}")



def main():
    args = parse_args()

    # ── Validación de entrada ──────────────────────────────────────────────
    if not os.path.isfile(args.audio):
        report_progress("error", f"No se encuentra el archivo: '{args.audio}'", json_mode=args.json_mode)
        sys.exit(1)

    # ── Ruta de salida ─────────────────────────────────────────────────────
    if args.output:
        output_path = args.output
    else:
        base = os.path.splitext(args.audio)[0]
        output_path = base + "_chapters.m4b"

    if not args.json_mode:
        report_progress("header", "CHAPTR — Generador de capítulos para audiolibros", json_mode=False)
        print(f"  Entrada : {args.audio}")
        print(f"  Salida  : {output_path}")
        print(f"  Whisper : {args.whisper_model}")
        print(f"  LLM     : {args.llm_model}")
        print("=" * 60)
    else:
        report_progress("info", "Iniciando proceso...", json_mode=True)

    t_start = time.time()

    # ── FASE B: Detección (Solo si no es --export-only) ────────────────────
    chapters = []
    if not args.export_only:
        # ── PASO 1: Transcripción ──────────────────────────────────────────────
        if args.skip_transcription:
            if not args.transcript:
                report_progress("error", "--skip-transcription requiere --transcript <ruta.json>", json_mode=args.json_mode)
                sys.exit(1)
            report_progress("progress", f"Cargando transcripción desde '{args.transcript}'...", step=1, percent=0.1, json_mode=args.json_mode)
            segments = transcriber.load_transcript(args.transcript)
            report_progress("success", f"{len(segments)} segmentos cargados.", json_mode=args.json_mode)
        else:
            report_progress("progress", f"Transcribiendo audio con Whisper ({args.whisper_model})...", step=1, percent=0.0, json_mode=args.json_mode)
            t0 = time.time()
            segments = transcriber.transcribe(args.audio, model_size=args.whisper_model)
            report_progress("success", f"Transcripción completada en {time.time() - t0:.1f} s", json_mode=args.json_mode)

            if args.save_transcript:
                transcript_path = os.path.splitext(args.audio)[0] + "_transcript.json"
                transcriber.save_transcript(segments, transcript_path)

        # ── PASO 2: Detección de capítulos ────────────────────────────────────
        report_progress("progress", f"Detectando capítulos con {args.llm_model} via Ollama...", step=2, percent=0.4, json_mode=args.json_mode)
        t0 = time.time()
        chapters = detector.detect_chapters(
            segments,
            model=args.llm_model,
            ollama_host=args.ollama_host,
        )
        report_progress("success", f"Capítulos detectados en {time.time() - t0:.1f} s", json_mode=args.json_mode)
        
        # Si solo queremos detectar, soltamos el JSON y terminamos
        if args.detect_only:
            if args.json_mode:
                print(json.dumps({"type": "chapters_data", "chapters": chapters}), flush=True)
            else:
                print("\n  Capítulos detectados:")
                for i, ch in enumerate(chapters):
                    m = int(ch["start_seconds"] // 60)
                    s = ch["start_seconds"] % 60
                    print(f"    {i+1:2d}. [{m:02d}:{s:05.2f}] {ch['title']}")
            sys.exit(0)
    else:
        # Cargar capítulos desde el argumento si es --export-only
        if not args.chapters_json:
            report_progress("error", "--export-only requiere --chapters-json", json_mode=args.json_mode)
            sys.exit(1)
        
        try:
            if os.path.isfile(args.chapters_json):
                with open(args.chapters_json, 'r', encoding='utf-8') as f:
                    chapters = json.load(f)
            else:
                chapters = json.loads(args.chapters_json)
        except Exception as e:
            report_progress("error", f"Error al cargar JSON de capítulos: {str(e)}", json_mode=args.json_mode)
            sys.exit(1)

    # ── FASE C: Exportar M4B (Solo si no es --detect-only) ─────────────────
    report_progress("progress", "Generando M4B con FFmpeg...", step=3, percent=0.7, json_mode=args.json_mode)
    t0 = time.time()
    
    # Metadatos del argumento si existen
    metadata = {}
    if args.title: metadata["title"] = args.title
    if args.author: metadata["author"] = args.author

    exporter.export_m4b(
        audio_path=args.audio,
        chapters=chapters,
        output_path=output_path,
        metadata=metadata,
        cover_path=args.cover
    )
    report_progress("success", f"M4B generado en {time.time() - t0:.1f} s", json_mode=args.json_mode)

    # ── Resumen final ──────────────────────────────────────────────────────
    total = time.time() - t_start
    if not args.json_mode:
        print()
        print("=" * 60)
        print(f"  ✅ ¡COMPLETADO! Tiempo total: {total:.1f} s ({total/60:.1f} min)")
        print(f"  📚 Archivo generado: {output_path}")
        print(f"  📖 Capítulos: {len(chapters)}")
        print("=" * 60)
    else:
        report_progress("result", output_path, json_mode=True)

    print()
    print("  Pasa el M4B a tu iPhone via Finder → sección Libros")
    print("  o arrástralo a la app Libros en tu Mac.")
    print()


if __name__ == "__main__":
    main()

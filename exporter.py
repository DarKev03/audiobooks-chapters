"""
exporter.py — Generación del archivo M4B con capítulos usando FFmpeg
"""

import subprocess
import os
import sys
import tempfile
import re


def _seconds_to_ms(seconds: float) -> int:
    """Convierte segundos a milisegundos (entero)."""
    return int(round(seconds * 1000))


def write_ffmetadata(chapters: list[dict], audio_duration_s: float, output_path: str) -> None:
    """
    Escribe el archivo de metadatos FFmpeg con los capítulos.

    Args:
        chapters: Lista de dicts con 'title' y 'start_seconds'
        audio_duration_s: Duración total del audio en segundos
        output_path: Ruta donde guardar el fichero .txt de metadatos
    """
    lines = [";FFMETADATA1\n"]

    for i, chapter in enumerate(chapters):
        start_ms = _seconds_to_ms(chapter["start_seconds"])

        # El END del capítulo es el START del siguiente, o el fin del audio
        if i + 1 < len(chapters):
            end_ms = _seconds_to_ms(chapters[i + 1]["start_seconds"])
        else:
            end_ms = _seconds_to_ms(audio_duration_s)

        # Asegurar que end > start
        if end_ms <= start_ms:
            end_ms = start_ms + 1000

        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={start_ms}")
        lines.append(f"END={end_ms}")
        lines.append(f"title={chapter['title']}")
        lines.append("")  # línea en blanco entre capítulos

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[Exporter] Metadatos escritos en '{output_path}'")


def get_audio_duration(audio_path: str) -> float:
    """Obtiene la duración del audio en segundos usando ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falló: {result.stderr}")
    return float(result.stdout.strip())


def export_m4b(
    audio_path: str,
    chapters: list[dict],
    output_path: str,
) -> None:
    """
    Genera el M4B final con los capítulos incrustados.
    Los metadatos del audio original (título, autor, portada...) se conservan.

    Args:
        audio_path: Ruta al audio original
        chapters: Lista de capítulos detectados
        output_path: Ruta del M4B de salida
    """
    print("[Exporter] Obteniendo duración del audio...")
    duration = get_audio_duration(audio_path)
    print(f"[Exporter] Duración: {duration:.1f} s ({duration/60:.1f} min)")

    # Archivo temporal para los metadatos de capítulos
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        meta_path = tmp.name

    try:
        write_ffmetadata(chapters, duration, meta_path)

        # Construir comando FFmpeg
        input_ext = os.path.splitext(audio_path)[1].lower()

        cmd = [
            "ffmpeg",
            "-y",                        # Sobreescribir sin preguntar
            "-i", audio_path,            # Audio original
            "-i", meta_path,             # Fichero solo con capítulos
            "-map_metadata", "0",        # Conservar metadatos del audio original
            "-map_chapters", "1",        # Usar capítulos del fichero temporal
            "-map", "0:a",               # Mapear audio
            "-map", "0:v?",              # Mapear video/portada (si existe)
        ]

        # Si el input ya es AAC (m4a/m4b), copiar directamente; si no, convertir
        if input_ext in (".m4a", ".m4b", ".aac"):
            cmd += ["-c:a", "copy"]
        else:
            # MP3 → AAC para máxima compatibilidad con Apple Books
            cmd += ["-c:a", "aac", "-b:a", "128k"]

        cmd += [
            "-c:v", "mjpeg",          # convierte PNG → JPEG
            "-vf", "scale=500:500",   # mantiene el tamaño
            "-q:v", "2",              # calidad alta
            "-disposition:v", "attached_pic",
            "-metadata:s:v", "title=Album cover",
            "-metadata:s:v", "comment=Cover (front)",
        ]

        cmd += ["-f", "mp4", output_path]

        print(f"[Exporter] Ejecutando FFmpeg...")
        
        # Usamos Popen para leer el progreso en tiempo real
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        # Regex para capturar el tiempo procesado: time=00:00:00.00
        time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

        def _time_to_seconds(h, m, s):
            return int(h) * 3600 + int(m) * 60 + float(s)

        while True:
            # FFmpeg envía las estadísticas a stderr
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            
            if "time=" in line:
                match = time_regex.search(line)
                if match:
                    h, m, s = match.groups()
                    current_s = _time_to_seconds(h, m, s)
                    
                    percent = (current_s / duration) * 100
                    percent = min(100.0, percent)
                    
                    # Formatear tiempos para el log
                    curr_fmt = f"{int(current_s//60):02d}:{current_s%60:05.2f}"
                    total_fmt = f"{int(duration//60):02d}:{duration%60:05.2f}"
                    
                    # \r para sobreescribir la misma línea en la terminal
                    sys.stdout.write(f"\r[Exporter] Progreso: {percent:5.1f}% | {curr_fmt} / {total_fmt} ")
                    sys.stdout.flush()

        process.wait()
        print() # Nueva línea tras terminar el bucle de progreso

        if process.returncode != 0:
            # Si falló, mostramos lo que haya quedado en stderr
            err_output = process.stderr.read()
            print(f"[Exporter] ❌ FFmpeg falló. Stderr:\n{err_output}")
            raise RuntimeError("FFmpeg falló al generar el M4B.")

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[Exporter] ✅ M4B generado: '{output_path}' ({size_mb:.1f} MB)")

    finally:
        if os.path.exists(meta_path):
            os.remove(meta_path)

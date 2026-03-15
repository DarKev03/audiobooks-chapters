# Chaptr 📚

> Herramienta local que detecta los capítulos de un audiolibro y genera un **M4B con capítulos nativos** compatible con la app **Libros de iPhone/Mac**.

Sin APIs externas. Sin coste. Completamente offline.

---

## ¿Cómo funciona?

```
Audio MP3/M4A/M4B
      │
      ▼
[Whisper GPU] ──► Transcripción con timestamps
      │
      ▼
[Llama 3.2 / Ollama] ──► Lista de capítulos detectados
      │
      ▼
[FFmpeg] ──► M4B con capítulos incrustados
```

1. **Whisper** transcribe el audio en español con timestamps precisos
2. **Llama 3.2** (via Ollama, local) analiza la transcripción y detecta dónde anuncia el narrador cada capítulo
3. **FFmpeg** empaqueta el audio original + los metadatos de capítulos en un M4B

---

## Requisitos previos

| Herramienta | Versión | Notas |
|---|---|---|
| Python | 3.11+ | — |
| CUDA | 12.x | Para GPU |
| FFmpeg | 6+ | Debe estar en el PATH |
| Ollama | cualquiera | `ollama serve` antes de ejecutar |
| Llama 3.2 | — | `ollama pull llama3.2` |

### Instalar dependencias Python

```bash
pip install -r requirements.txt
```

---

## Uso

```bash
# Uso básico
python main.py libro.mp3

# Especificar título y autor (se incrustan en el M4B)
python main.py libro.m4a --title "El Imperio Final" --author "Brandon Sanderson"

# Usar modelo Whisper más potente (más lento pero más preciso)
python main.py libro.mp3 --whisper-model large-v3

# Guardar la transcripción para no repetirla
python main.py libro.mp3 --save-transcript

# Reutilizar transcripción ya guardada (salta el paso de Whisper)
python main.py libro.mp3 --skip-transcription --transcript libro_transcript.json

# Salida personalizada
python main.py libro.mp3 -o "Biblioteca/MiLibro_chapters.m4b"
```

### Opciones disponibles

| Opción | Default | Descripción |
|---|---|---|
| `--output / -o` | `*_chapters.m4b` | Ruta del archivo de salida |
| `--title / -t` | — | Título del audiolibro |
| `--author / -a` | — | Autor del audiolibro |
| `--whisper-model` | `medium` | `tiny` · `base` · `small` · `medium` · `large` · `large-v3` |
| `--llm-model` | `llama3.2` | Cualquier modelo instalado en Ollama |
| `--ollama-host` | `http://localhost:11434` | URL del servidor Ollama |
| `--save-transcript` | off | Guarda la transcripción JSON |
| `--skip-transcription` | off | Carga transcripción desde `--transcript` |

---

## Flujo de trabajo recomendado

```bash
# 1. Arrancar Ollama (una sola vez, en otra terminal)
ollama serve

# 2. Primera ejecución: guardar transcripción para poder iterar
python main.py "El Imperio Final.mp3" \
  --title "El Imperio Final" \
  --author "Brandon Sanderson" \
  --save-transcript

# 3. Si los capítulos no son correctos, re-ejecutar sin transcribir de nuevo
python main.py "El Imperio Final.mp3" \
  --skip-transcription \
  --transcript "El Imperio Final_transcript.json" \
  --llm-model llama3.2
```

---

## Estructura del proyecto

```
chaptr/
├── main.py          # Orquestador y CLI
├── transcriber.py   # Whisper (GPU) → segmentos con timestamps
├── detector.py      # Ollama/Llama → lista de capítulos
├── exporter.py      # FFmpeg → M4B con capítulos
└── requirements.txt # Dependencias Python
```

---

## Transferir a iPhone

1. Conecta el iPhone al Mac via cable o Wi-Fi
2. Abre **Finder** → selecciona tu iPhone → pestaña **Libros**
3. Arrastra el `.m4b` generado
4. Abre la app **Libros** en el iPhone → sección **Audiolibros**

> Los capítulos aparecerán en el reproductor y podrás navegar entre ellos.

---

## Notas técnicas

- El audio MP3 se **convierte a AAC 128k** al empaquetar en M4B. Los M4A/M4B se copian **sin recodificar** (más rápido, sin pérdida de calidad).
- Los timestamps del fichero de metadatos están en **milisegundos** (formato FFmpeg).
- Whisper se ejecuta siempre en **CUDA** si está disponible; si no, cae a CPU automáticamente.
- El prompt del LLM está diseñado para que la respuesta sea **JSON puro** sin texto adicional, con fallback si el parseo falla.

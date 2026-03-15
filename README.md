# Chaptr 📚

> Herramienta local que detecta los capítulos de un audiolibro y genera un **M4B con capítulos nativos** compatible con la app **Libros de iPhone/Mac**. Completamente offline y optimizado para precisión y velocidad.

---

## ¿Cómo funciona?

```
Audio MP3/M4A/M4B
      │
      ▼
[Whisper GPU] ───────► Transcripción con timestamps precisos
      │
      ▼
[Detección Híbrida] ──► 1. Filtro de silencios largos + segmentos cortos
      │                 2. Validación con LLM (Mistral:7b vía Ollama)
      │                 3. Re-mapeo del texto original
      │
      ▼
[FFmpeg Premium] ────► M4B final con capítulos, metadatos y portadas
```

1. **Transcripción**: Whisper genera el texto con tiempos exactos.
2. **Detección Híbrida**: 
   - Se filtran candidatos mediante pausas en el audio (silencios > 2.5s).
   - **Mistral:7b** actúa como juez para confirmar cuáles son capítulos reales.
   - El sistema sincroniza la decisión del LLM con el texto original de Whisper para asegurar títulos 100% fieles.
3. **Exportación**: FFmpeg empaqueta todo. Si el audio es MP3, se convierte a AAC 128k para compatibilidad total con iOS.

---

## Características principales

- **0% Alucinaciones**: Los títulos de los capítulos nunca son "inventados" por la IA; siempre provienen del audio original.
- **Soporte de Portadas**: Conserva la carátula original del libro (o la incrusta correctamente como `attached_pic`).
- **Barra de Progreso**: Visualización en tiempo real durante la generación del archivo final.
- **Iteración Rápida**: Puedes saltar la transcripción (`--skip-transcription`) para probar diferentes modelos o parámetros en segundos una vez tienes el JSON.
- **Parsing Resiliente**: Capaz de entender respuestas del LLM incluso si el formato JSON no es perfecto.

---

## Requisitos previos

| Herramienta | Versión | Notas |
|---|---|---|
| Python | 3.11+ | — |
| CUDA | 12.x | Recomendado para Whisper GPU |
| FFmpeg | 6+ | Debe estar en el PATH del sistema |
| Ollama | Última | Servidor local de LLM |
| Mistral | 7b | `ollama pull mistral:7b` (Modelo por defecto) |

### Instalación

```bash
# Clonar y configurar entorno
git clone ...
cd audiobooks-chapters
python -m venv .venv
source .venv/bin/activate  # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
```

---

## Uso

### Comandos comunes

```bash
# Uso estándar (MP3 a M4B con capítulos)
python main.py "Libro.mp3"

# Con metadatos personalizados
python main.py "Libro.mp3" --title "Título" --author "Autor"

# Guardar transcripción para iterar después
python main.py "Libro.mp3" --save-transcript

# Re-generar capítulos sin repetir el paso de Whisper
python main.py "Libro.mp3" --skip-transcription --transcript "Libro_transcript.json"

# Cambiar de modelo LLM al vuelo
python main.py "Libro.mp3" --llm-model llama3.1:8b
```

### Opciones avanzadas

| Opción | Default | Descripción |
|---|---|---|
| `--llm-model` | `mistral:7b` | Modelo en Ollama para validar capítulos |
| `--whisper-model` | `small` | Tamaño del modelo (base, small, medium, large-v3...) |
| `--ollama-host` | `http://localhost:11434` | Endpoint de tu servidor Ollama |
| `-o / --output` | `(auto)` | Ruta del M4B de salida |

---

## Desarrollo y VS Code

El proyecto incluye un archivo `.vscode/launch.json` configurado para depurar cómodamente:
- **Flujo completo**: Procesa el audio de principio a fin.
- **Saltar transcripción**: Ideal para ajustar el prompt o la lógica del `detector.py`.

---

## Créditos y Tecnología

- **OpenAI Whisper**: Transcripción SOTA.
- **Ollama/Mistral**: Inteligencia local para análisis estructural.
- **FFmpeg**: El motor multimedia.

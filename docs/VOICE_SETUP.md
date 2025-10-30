# Voice Setup Guide

The assistant can convert farmer voice notes into commands and send audio summaries back. All components rely on free/open tooling.

## 1. Download Vosk Offline Models
Create the `voice/` folder (already committed) and download language models you need:

```bash
# Hindi small model (~50 MB)
curl -L -o voice/vosk-model-small-hi-0.22.zip \
  https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip
unzip voice/vosk-model-small-hi-0.22.zip -d voice/

# English fallback model
curl -L -o voice/vosk-model-small-en-us-0.15.zip \
  https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip voice/vosk-model-small-en-us-0.15.zip -d voice/
```

The assistant automatically picks the right model based on the farmer’s preferred language. If a model is missing, voice understanding gracefully falls back to text prompts.

## 2. Install ffmpeg
Telegram voice notes arrive as OGG/Opus files. `pydub` requires `ffmpeg` to convert these into WAV (16 kHz, mono) before running Vosk.

- **macOS (Homebrew)**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **Windows**: download binaries from https://ffmpeg.org/download.html and add to `PATH`.

## 3. Text-to-Speech Cache
The assistant uses gTTS to render audio summaries and caches them under `data/cache/tts/`. To pre-generate audio clips for offline use, run:

```bash
python scripts/precache.py
```

gTTS requires intermittent internet the first time a phrase is generated. Afterwards cached MP3 files are reused offline.

## 4. Field Usage Tips
- Encourage farmers to hold the phone close and speak slowly in their native language.
- If reception is poor, advise them to send shorter commands (commodity, market, quantity) which are easier to decode.
- You can also supply templated text responses alongside audio so family members can read along.

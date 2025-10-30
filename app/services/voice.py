from __future__ import annotations

import audioop
import json
import wave
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from app.config import CACHE_DIR

VOICE_DIR = Path("voice")
VOICE_DIR.mkdir(exist_ok=True)


class VoiceService:
    """Handles speech-to-text and text-to-speech with offline-first approach."""

    def __init__(self) -> None:
        self.tts_cache = CACHE_DIR / "tts"
        self.tts_cache.mkdir(parents=True, exist_ok=True)

    def _load_vosk_model(self, language: str):
        try:
            from vosk import Model  # type: ignore
        except Exception:
            return None

        language_map = {
            "hi": "vosk-model-small-hi-0.22",
            "en": "vosk-model-small-en-us-0.15",
            "mr": "vosk-model-small-hi-0.22",
        }
        model_folder = language_map.get(language, "vosk-model-small-hi-0.22")
        model_path = VOICE_DIR / model_folder
        if not model_path.exists():
            return None
        try:
            model = Model(str(model_path))
            return model
        except Exception:
            return None

    def _normalize_audio(self, original: Path) -> Optional[Path]:
        try:
            with wave.open(str(original), "rb") as wf:
                if (
                    wf.getnchannels() == 1
                    and wf.getsampwidth() == 2
                    and wf.getframerate() == 16000
                ):
                    return original
        except wave.Error:
            pass

        try:
            with wave.open(str(original), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
        except wave.Error:
            return None

        if channels != 1:
            frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
            channels = 1
        if frame_rate != 16000:
            frames, _ = audioop.ratecv(frames, sample_width, channels, frame_rate, 16000, None)
            frame_rate = 16000
        if sample_width != 2:
            frames = audioop.lin2lin(frames, sample_width, 2)
            sample_width = 2

        tmp_file = NamedTemporaryFile(suffix=".wav", delete=False, dir=VOICE_DIR)
        with wave.open(tmp_file.name, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(frame_rate)
            wf.writeframes(frames)
        tmp_file.close()
        return Path(tmp_file.name)

    def speech_to_text(self, audio_path: Path, language: str = "hi") -> Optional[str]:
        try:
            from vosk import KaldiRecognizer  # type: ignore
        except Exception:
            return None

        model = self._load_vosk_model(language)
        if not model:
            return None

        prepared = self._normalize_audio(audio_path)
        if not prepared:
            return None

        rec = KaldiRecognizer(model, 16000)
        try:
            with wave.open(str(prepared), "rb") as wf:
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    rec.AcceptWaveform(data)
        finally:
            if prepared != audio_path:
                try:
                    prepared.unlink()
                except FileNotFoundError:
                    pass

        try:
            final_text = json.loads(rec.FinalResult()).get("text") or ""
            return final_text.strip() or None
        except json.JSONDecodeError:
            return None

    def text_to_speech(
        self,
        text: str,
        language: str,
        output_file: Path,
    ) -> Optional[Path]:
        try:
            from gtts import gTTS  # type: ignore
        except Exception:
            return None
        cached_file = self.tts_cache / f"{hash((text, language))}.mp3"
        if cached_file.exists():
            output_file.write_bytes(cached_file.read_bytes())
            return output_file
        try:
            tts = gTTS(text=text, lang=language)
            tts.save(str(output_file))
            cached_file.write_bytes(output_file.read_bytes())
            return output_file
        except Exception:
            return None

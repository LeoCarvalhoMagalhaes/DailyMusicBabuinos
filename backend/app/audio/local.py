"""Provedor de arquivos locais licenciados (MP3 ou WAV PCM 16 bits).

Para usar músicas próprias ou com licença: coloque `<slug>.mp3` (ou `.wav`) em
AUDIO_LOCAL_DIR, onde `<slug>` é o identificador da faixa no catálogo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.audio.base import AudioClip, AudioProvider
from app.audio.mp3 import Mp3FormatError, trim_mp3
from app.audio.wav import WavFormatError, trim_wav
from app.core.errors import AudioUnavailableError
from app.models import MusicTrack


class LocalFileProvider(AudioProvider):
    name = "local"
    max_seconds = 600.0
    attribution = "Áudio licenciado pelo operador do jogo"

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory).resolve()

    def _path(self, track: MusicTrack) -> Path | None:
        name = track.audio_ref or track.slug
        for ext in (".mp3", ".wav"):
            candidate = (self.directory / f"{name}{ext}").resolve()
            # Impede path traversal via audio_ref.
            if candidate.parent == self.directory and candidate.is_file():
                return candidate
        return None

    def check_availability(self, track: MusicTrack) -> bool:
        available = self._path(track) is not None
        track.availability = "available" if available else "unavailable"
        track.availability_checked_at = datetime.now(UTC)
        return available

    def get_clip(self, track: MusicTrack, seconds: float, category: str | None = None) -> AudioClip:
        path = self._path(track)
        if path is None:
            raise AudioUnavailableError("Arquivo de áudio não encontrado.")
        data = path.read_bytes()
        try:
            if path.suffix == ".mp3":
                clip, duration = trim_mp3(data, seconds)
                return AudioClip(clip, "audio/mpeg", duration)
            clip, duration = trim_wav(data, seconds)
            return AudioClip(clip, "audio/wav", duration)
        except (Mp3FormatError, WavFormatError) as exc:
            raise AudioUnavailableError("Arquivo de áudio inválido.") from exc

